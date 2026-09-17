"""
Recoverable Background Job Manager & Backpressure Controller for AeroCast-Now AI.
Phase 11 Platform Hardening — Reliability & Process Recovery.

Features:
1. Persistent Job Ledger backed by SQLite (`background_jobs`).
2. Job Lifecycle: QUEUED -> RUNNING -> SUCCEEDED / FAILED / RETRYING / CANCELLED.
3. Post-Restart Stale Job Recovery.
4. Bounded Queue Backpressure with Explicit Drop Audit.
"""
from __future__ import annotations

import uuid
import json
import logging
from enum import Enum
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

from db.database import get_db
from .logging import get_logger

logger = get_logger("aerocast.jobs")


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    CANCELLED = "CANCELLED"
    RECOVERED = "RECOVERED"


class JobManager:
    """Manages persistent background jobs with heartbeat tracking and restart recovery."""

    def __init__(self, max_queue_depth: int = 100):
        self.max_queue_depth = max_queue_depth
        self._init_schema()
        self.recover_stale_jobs_on_boot()

    def _init_schema(self):
        db = get_db()
        db.execute("""
            CREATE TABLE IF NOT EXISTS background_jobs (
                job_id TEXT PRIMARY KEY,
                job_type TEXT NOT NULL,
                status TEXT NOT NULL,
                parameters_json TEXT,
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                created_at TEXT NOT NULL,
                started_at TEXT,
                ended_at TEXT,
                last_heartbeat TEXT,
                failure_reason TEXT
            );
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_job_status ON background_jobs (status);")
        db.execute("CREATE INDEX IF NOT EXISTS idx_job_type ON background_jobs (job_type);")

    def enqueue_job(
        self, job_type: str, parameters: Dict[str, Any], max_retries: int = 3
    ) -> Optional[str]:
        """
        Enqueues a new background job.
        Enforces backpressure: if active queue depth exceeds limit, rejects job and logs drop audit.
        """
        db = get_db()
        # Count queued jobs
        row = db.fetch_one("SELECT COUNT(*) as cnt FROM background_jobs WHERE status = 'QUEUED'")
        active_queued = row["cnt"] if row else 0

        if active_queued >= self.max_queue_depth:
            now = datetime.now(timezone.utc).isoformat()
            logger.warning(
                f"Backpressure applied: dropped job {job_type}. Queue depth {active_queued}/{self.max_queue_depth}",
                extra={"event": "job_dropped_backpressure", "job_type": job_type, "status": "dropped"},
            )
            # Record in audit log
            db.execute(
                """
                INSERT INTO audit_log (timestamp, actor, action, entity_type, entity_id, details_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    "job_manager",
                    "DROP_BACKPRESSURE",
                    "background_job",
                    job_type,
                    json.dumps({"reason": "queue_full", "limit": self.max_queue_depth, "depth": active_queued}),
                ),
            )
            return None

        job_id = f"job-{uuid.uuid4().hex[:12]}"
        now_str = datetime.now(timezone.utc).isoformat()
        db.execute(
            """
            INSERT INTO background_jobs (
                job_id, job_type, status, parameters_json, retry_count, max_retries, created_at
            ) VALUES (?, ?, ?, ?, 0, ?, ?)
            """,
            (job_id, job_type, JobStatus.QUEUED.value, json.dumps(parameters), max_retries, now_str),
        )
        return job_id

    def start_job(self, job_id: str) -> None:
        """Marks a job as RUNNING with current heartbeat timestamp."""
        now_str = datetime.now(timezone.utc).isoformat()
        db = get_db()
        db.execute(
            """
            UPDATE background_jobs 
            SET status = ?, started_at = ?, last_heartbeat = ? 
            WHERE job_id = ?
            """,
            (JobStatus.RUNNING.value, now_str, now_str, job_id),
        )

    def heartbeat(self, job_id: str) -> None:
        """Updates job heartbeat timestamp."""
        now_str = datetime.now(timezone.utc).isoformat()
        db = get_db()
        db.execute("UPDATE background_jobs SET last_heartbeat = ? WHERE job_id = ?", (now_str, job_id))

    def complete_job(self, job_id: str, success: bool, failure_reason: Optional[str] = None) -> None:
        """Transitions job to SUCCEEDED or FAILED."""
        now_str = datetime.now(timezone.utc).isoformat()
        db = get_db()
        status = JobStatus.SUCCEEDED.value if success else JobStatus.FAILED.value
        db.execute(
            """
            UPDATE background_jobs 
            SET status = ?, ended_at = ?, failure_reason = ? 
            WHERE job_id = ?
            """,
            (status, now_str, failure_reason, job_id),
        )

    def recover_stale_jobs_on_boot(self, heartbeat_timeout_minutes: int = 15) -> List[str]:
        """
        Scans for jobs left in RUNNING status during a process crash/restart
        and transitions them to RECOVERED or allows idempotent restart.
        """
        db = get_db()
        stale_jobs = db.fetch_all(
            "SELECT job_id, job_type FROM background_jobs WHERE status = 'RUNNING'"
        )
        recovered_ids = []
        now_str = datetime.now(timezone.utc).isoformat()
        for job in stale_jobs:
            jid = job["job_id"]
            db.execute(
                """
                UPDATE background_jobs 
                SET status = ?, ended_at = ?, failure_reason = 'Process restarted during execution' 
                WHERE job_id = ?
                """,
                (JobStatus.RECOVERED.value, now_str, jid),
            )
            recovered_ids.append(jid)
            logger.info(f"Recovered orphan job {jid} of type {job['job_type']}")

        return recovered_ids

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        db = get_db()
        return db.fetch_one("SELECT * FROM background_jobs WHERE job_id = ?", (job_id,))

    def list_recent_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        db = get_db()
        return db.fetch_all("SELECT * FROM background_jobs ORDER BY created_at DESC LIMIT ?", (limit,))


job_manager = JobManager()

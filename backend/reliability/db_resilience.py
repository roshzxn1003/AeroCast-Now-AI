"""
Database Resilience, Idempotency & Transaction Safety for AeroCast-Now AI.
Phase 11 Platform Hardening — Persistent State Reliability.

Provides:
1. Jittered Exponential Backoff for SQLite `database is locked` contention.
2. Atomic Transaction Context Managers with safe rollback.
3. Idempotency Key Tracking to guarantee duplicate network retries do not create duplicate records.
"""
from __future__ import annotations

import time
import random
import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Callable

from db.database import get_db
from .logging import get_logger

logger = get_logger("aerocast.db_resilience")


def execute_with_retry(
    operation: Callable[[], Any],
    max_retries: int = 5,
    base_backoff_sec: float = 0.05,
    max_backoff_sec: float = 1.0,
) -> Any:
    """Executes a database callable with exponential backoff and randomized jitter on lock contention."""
    attempt = 0
    while True:
        try:
            return operation()
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() or "busy" in str(e).lower():
                attempt += 1
                if attempt > max_retries:
                    logger.error(f"Database contention exceeded max retries ({max_retries}): {e}")
                    raise
                # Exponential backoff with Full Jitter
                backoff = min(max_backoff_sec, base_backoff_sec * (2 ** (attempt - 1)))
                sleep_duration = random.uniform(0, backoff)
                logger.warning(
                    f"Database locked, retrying in {sleep_duration:.3f}s (attempt {attempt}/{max_retries})"
                )
                time.sleep(sleep_duration)
            else:
                raise


@contextmanager
def atomic_transaction(db_manager=None):
    """
    Context manager providing atomic multi-statement transaction safety.
    Guarantees automatic rollback on error.
    """
    db = db_manager or get_db()
    conn = db._get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE TRANSACTION;")
        yield conn
        conn.execute("COMMIT;")
    except Exception as e:
        try:
            conn.execute("ROLLBACK;")
        except Exception:
            pass
        logger.error(f"Transaction aborted and rolled back due to error: {e}")
        raise


class IdempotencyLedger:
    """Stores and resolves idempotency keys to ensure network retries are non-duplicating."""

    @staticmethod
    def init_schema():
        db = get_db()
        db.execute("""
            CREATE TABLE IF NOT EXISTS idempotency_ledger (
                idempotency_key TEXT PRIMARY KEY,
                endpoint TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                response_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_idem_key ON idempotency_ledger (idempotency_key);")

    @classmethod
    def get_cached_response(cls, key: str) -> Optional[Dict[str, Any]]:
        """Retrieves non-expired cached response for given idempotency key."""
        cls.init_schema()
        db = get_db()
        now = datetime.now(timezone.utc).isoformat()
        row = db.fetch_one(
            "SELECT * FROM idempotency_ledger WHERE idempotency_key = ? AND expires_at > ?",
            (key, now),
        )
        if row:
            return {
                "status_code": row["status_code"],
                "data": json.loads(row["response_json"]),
                "cached": True,
            }
        return None

    @classmethod
    def record_response(
        cls, key: str, endpoint: str, status_code: int, response_data: Any, ttl_hours: int = 24
    ) -> None:
        """Stores API response against idempotency key."""
        cls.init_schema()
        db = get_db()
        now = datetime.now(timezone.utc)
        expires = (now + timedelta(hours=ttl_hours)).isoformat()
        db.execute(
            """
            INSERT OR REPLACE INTO idempotency_ledger (
                idempotency_key, endpoint, status_code, response_json, created_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (key, endpoint, status_code, json.dumps(response_data), now.isoformat(), expires),
        )

"""
AeroCast-Now AI: Database Migration & Schema Versioning Engine
============================================================
Provides versioned, reversible, and auditable database migrations for SQLite.
Enforces pre-migration backup snapshots and atomic transactions.
Never drops/recreates production databases.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Tuple


class Migration(NamedTuple):
    version: int
    name: str
    up_sql: str
    down_sql: str


# ==============================================================================
# VERSIONED MIGRATION REGISTRY
# ==============================================================================

MIGRATIONS: List[Migration] = [
    Migration(
        version=1,
        name="001_core_schema",
        up_sql="""
        CREATE TABLE IF NOT EXISTS observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            obs_id TEXT UNIQUE NOT NULL,
            source TEXT NOT NULL,
            dataset TEXT NOT NULL,
            observation_time TEXT NOT NULL,
            ingested_at TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            coverage_bbox TEXT,
            variable TEXT NOT NULL,
            unit TEXT NOT NULL,
            value_numeric REAL,
            payload_json TEXT,
            quality_status TEXT NOT NULL CHECK (quality_status IN ('VALID', 'SUSPECT', 'MISSING', 'STALE', 'INVALID')),
            quality_reason TEXT,
            processing_version TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_obs_time_source ON observations (observation_time, source);
        CREATE INDEX IF NOT EXISTS idx_obs_variable ON observations (variable);
        CREATE INDEX IF NOT EXISTS idx_obs_quality ON observations (quality_status);

        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prediction_id TEXT UNIQUE NOT NULL,
            model_id TEXT NOT NULL,
            model_version TEXT NOT NULL,
            model_hash TEXT NOT NULL,
            station TEXT,
            generated_at TEXT NOT NULL,
            valid_time TEXT NOT NULL,
            lead_time_min INTEGER NOT NULL,
            max_dbz REAL,
            max_vil REAL,
            has_jump INTEGER DEFAULT 0,
            storm_count INTEGER DEFAULT 0,
            input_timestamps_json TEXT,
            data_sources_json TEXT,
            prediction_payload_json TEXT,
            verified INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_pred_valid_time ON predictions (valid_time);
        CREATE INDEX IF NOT EXISTS idx_pred_station_lead ON predictions (station, lead_time_min);
        CREATE INDEX IF NOT EXISTS idx_pred_verified ON predictions (verified);

        CREATE TABLE IF NOT EXISTS verifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            verification_id TEXT UNIQUE NOT NULL,
            prediction_id TEXT NOT NULL,
            verified_at TEXT NOT NULL,
            lead_time_min INTEGER NOT NULL,
            actual_max_dbz REAL,
            predicted_max_dbz REAL,
            error_dbz REAL,
            csi REAL,
            pod REAL,
            far REAL,
            hss REAL,
            jump_correct INTEGER,
            false_alarm INTEGER,
            missed_event INTEGER,
            FOREIGN KEY (prediction_id) REFERENCES predictions(prediction_id)
        );
        CREATE INDEX IF NOT EXISTS idx_verif_pred ON verifications (prediction_id);
        CREATE INDEX IF NOT EXISTS idx_verif_time ON verifications (verified_at);

        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id TEXT UNIQUE NOT NULL,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            urgency TEXT NOT NULL,
            headline TEXT NOT NULL,
            description TEXT,
            area_desc TEXT,
            cap_xml TEXT,
            sent_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            status TEXT NOT NULL,
            target_sectors TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_alert_status ON alerts (status);
        CREATE INDEX IF NOT EXISTS idx_alert_sent ON alerts (sent_at);

        CREATE TABLE IF NOT EXISTS model_registry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id TEXT UNIQUE NOT NULL,
            model_name TEXT NOT NULL,
            version TEXT NOT NULL,
            stage TEXT NOT NULL CHECK (stage IN ('EXPERIMENTAL', 'CANDIDATE', 'VALIDATED', 'STAGING', 'PRODUCTION', 'RETIRED', 'REJECTED', 'TRAINING', 'VALIDATION')),
            architecture TEXT NOT NULL,
            dataset_version TEXT NOT NULL,
            feature_version TEXT NOT NULL,
            weights_path TEXT NOT NULL,
            model_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            promoted_at TEXT,
            promoted_by TEXT,
            metrics_json TEXT,
            limitations_json TEXT,
            is_active_production INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_model_stage ON model_registry (stage);
        CREATE INDEX IF NOT EXISTS idx_model_prod ON model_registry (is_active_production);

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_id TEXT UNIQUE NOT NULL,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            component TEXT NOT NULL,
            details_json TEXT,
            checksum TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_log (timestamp);
        """,
        down_sql="""
        DROP TABLE IF EXISTS audit_log;
        DROP TABLE IF EXISTS model_registry;
        DROP TABLE IF EXISTS alerts;
        DROP TABLE IF EXISTS verifications;
        DROP TABLE IF EXISTS predictions;
        DROP TABLE IF EXISTS observations;
        """
    ),
    Migration(
        version=2,
        name="002_phase9_ingestion",
        up_sql="""
        CREATE TABLE IF NOT EXISTS raw_ingestion_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ingestion_id TEXT UNIQUE NOT NULL,
            source_provider TEXT NOT NULL,
            dataset TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            file_size_bytes INTEGER,
            ingested_at TEXT NOT NULL,
            observation_time TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('STORED', 'PROCESSED', 'FAILED', 'DUPLICATE')),
            error_message TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_raw_hash ON raw_ingestion_log (file_hash);
        CREATE INDEX IF NOT EXISTS idx_raw_provider_time ON raw_ingestion_log (source_provider, observation_time);

        CREATE TABLE IF NOT EXISTS provider_status (
            provider_id TEXT UNIQUE NOT NULL PRIMARY KEY,
            name TEXT NOT NULL,
            source_type TEXT NOT NULL,
            state TEXT NOT NULL CHECK (state IN ('HEALTHY', 'DEGRADED', 'OPEN', 'HALF_OPEN')),
            consecutive_failures INTEGER DEFAULT 0,
            total_requests INTEGER DEFAULT 0,
            total_failures INTEGER DEFAULT 0,
            last_success_time TEXT,
            last_failure_time TEXT,
            last_latency_ms REAL,
            fallback_count INTEGER DEFAULT 0,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS fallback_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT UNIQUE NOT NULL,
            source_type TEXT NOT NULL,
            primary_provider TEXT NOT NULL,
            secondary_provider TEXT NOT NULL,
            fallback_reason TEXT,
            timestamp TEXT NOT NULL,
            restored_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_fallback_time ON fallback_events (timestamp);
        CREATE INDEX IF NOT EXISTS idx_fallback_type ON fallback_events (source_type);

        CREATE TABLE IF NOT EXISTS data_quality_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            obs_id TEXT NOT NULL,
            source_provider TEXT NOT NULL,
            variable TEXT NOT NULL,
            qc_flag TEXT NOT NULL,
            qc_rule TEXT NOT NULL,
            observed_value REAL,
            expected_range TEXT,
            timestamp TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_qc_obs_time ON data_quality_log (timestamp, variable);
        CREATE INDEX IF NOT EXISTS idx_qc_flag ON data_quality_log (qc_flag);
        """,
        down_sql="""
        DROP TABLE IF EXISTS data_quality_log;
        DROP TABLE IF EXISTS fallback_events;
        DROP TABLE IF EXISTS provider_status;
        DROP TABLE IF EXISTS raw_ingestion_log;
        """
    ),
    Migration(
        version=3,
        name="003_phase10_monitoring",
        up_sql="""
        CREATE TABLE IF NOT EXISTS model_artifacts (
            artifact_id TEXT UNIQUE NOT NULL PRIMARY KEY,
            model_id TEXT NOT NULL,
            version TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            file_size_bytes INTEGER,
            framework_version TEXT,
            python_version TEXT,
            created_at TEXT NOT NULL,
            verified_at TEXT,
            status TEXT NOT NULL CHECK (status IN ('VALID', 'CORRUPT', 'MISSING'))
        );
        CREATE INDEX IF NOT EXISTS idx_art_model ON model_artifacts (model_id, version);
        CREATE INDEX IF NOT EXISTS idx_art_hash ON model_artifacts (file_hash);

        CREATE TABLE IF NOT EXISTS multi_horizon_verifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            verification_id TEXT UNIQUE NOT NULL,
            prediction_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            model_version TEXT NOT NULL,
            horizon_min INTEGER NOT NULL,
            initialization_time TEXT NOT NULL,
            valid_time TEXT NOT NULL,
            verified_at TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('VERIFIED', 'UNAVAILABLE', 'FAILED', 'PENDING')),
            mae REAL,
            rmse REAL,
            bias REAL,
            correlation REAL,
            threshold_dbz REAL DEFAULT 35.0,
            pod REAL,
            far REAL,
            csi REAL,
            hss REAL,
            ets REAL,
            f1 REAL,
            persistence_mae REAL,
            persistence_csi REAL,
            climatology_mae REAL,
            skill_score_vs_persistence REAL,
            notes TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_mh_pred ON multi_horizon_verifications (prediction_id);
        CREATE INDEX IF NOT EXISTS idx_mh_model_horizon ON multi_horizon_verifications (model_id, horizon_min);
        CREATE INDEX IF NOT EXISTS idx_mh_status ON multi_horizon_verifications (status);

        CREATE TABLE IF NOT EXISTS storm_events (
            event_id TEXT UNIQUE NOT NULL PRIMARY KEY,
            name TEXT,
            region TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            severity TEXT NOT NULL,
            max_observed_dbz REAL,
            max_predicted_dbz REAL,
            first_model_detection_time TEXT,
            first_observation_time TEXT,
            detection_lead_time_min REAL,
            location_error_km REAL,
            classification TEXT CHECK (classification IN ('DETECTED', 'MISSED', 'FALSE_ALARM')),
            false_alarm_cause TEXT,
            miss_contributing_factors TEXT,
            notes TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_storm_event_time ON storm_events (start_time);
        CREATE INDEX IF NOT EXISTS idx_storm_event_class ON storm_events (classification);

        CREATE TABLE IF NOT EXISTS drift_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evaluation_time TEXT NOT NULL,
            variable TEXT NOT NULL,
            metric_type TEXT NOT NULL,
            metric_value REAL NOT NULL,
            p_value REAL,
            drift_status TEXT NOT NULL CHECK (drift_status IN ('STABLE', 'WARNING', 'DRIFT_DETECTED')),
            baseline_period TEXT,
            current_period TEXT,
            details_json TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_drift_time_var ON drift_metrics (evaluation_time, variable);
        CREATE INDEX IF NOT EXISTS idx_drift_status ON drift_metrics (drift_status);

        CREATE TABLE IF NOT EXISTS retraining_requests (
            request_id TEXT UNIQUE NOT NULL PRIMARY KEY,
            model_id TEXT NOT NULL,
            current_version TEXT NOT NULL,
            trigger_type TEXT NOT NULL CHECK (trigger_type IN ('SCHEDULED', 'DATA_DRIFT', 'PERFORMANCE_DEGRADATION', 'NEW_DATASET', 'MANUAL')),
            trigger_reason TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('PENDING', 'APPROVED', 'IN_PROGRESS', 'EVALUATED', 'REJECTED', 'PROMOTED')),
            reviewed_by TEXT,
            reviewed_at TEXT,
            candidate_model_id TEXT,
            offline_eval_summary_json TEXT,
            notes TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_retrain_status ON retraining_requests (status);
        CREATE INDEX IF NOT EXISTS idx_retrain_model ON retraining_requests (model_id);

        CREATE TABLE IF NOT EXISTS experiments (
            experiment_id TEXT UNIQUE NOT NULL PRIMARY KEY,
            name TEXT NOT NULL,
            model_id TEXT NOT NULL,
            model_version TEXT NOT NULL,
            dataset_version TEXT NOT NULL,
            feature_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            training_period TEXT,
            holdout_test_period TEXT,
            hyperparameters_json TEXT,
            metrics_json TEXT,
            holdout_metrics_json TEXT,
            status TEXT NOT NULL,
            notes TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_exp_model ON experiments (model_id, model_version);

        CREATE TABLE IF NOT EXISTS model_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_id TEXT UNIQUE NOT NULL,
            timestamp TEXT NOT NULL,
            action_type TEXT NOT NULL CHECK (action_type IN ('TRAIN', 'EVALUATE', 'REGISTER', 'STAGE', 'PROMOTE', 'ROLLBACK', 'RETIRE', 'REJECT')),
            model_id TEXT NOT NULL,
            version TEXT NOT NULL,
            actor TEXT NOT NULL,
            reason TEXT NOT NULL,
            previous_state TEXT,
            new_state TEXT,
            details_json TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_action_model ON model_actions (model_id, timestamp);
        CREATE INDEX IF NOT EXISTS idx_action_type ON model_actions (action_type);
        """,
        down_sql="""
        DROP TABLE IF EXISTS model_actions;
        DROP TABLE IF EXISTS experiments;
        DROP TABLE IF EXISTS retraining_requests;
        DROP TABLE IF EXISTS drift_metrics;
        DROP TABLE IF EXISTS storm_events;
        DROP TABLE IF EXISTS multi_horizon_verifications;
        DROP TABLE IF EXISTS model_artifacts;
        """
    ),
    Migration(
        version=4,
        name="004_phase11_reliability",
        up_sql="""
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
        CREATE INDEX IF NOT EXISTS idx_job_status ON background_jobs (status);
        CREATE INDEX IF NOT EXISTS idx_job_type ON background_jobs (job_type);

        CREATE TABLE IF NOT EXISTS idempotency_ledger (
            idempotency_key TEXT PRIMARY KEY,
            endpoint TEXT NOT NULL,
            status_code INTEGER NOT NULL,
            response_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_idem_key ON idempotency_ledger (idempotency_key);
        """,
        down_sql="""
        DROP TABLE IF EXISTS idempotency_ledger;
        DROP TABLE IF EXISTS background_jobs;
        """
    ),
    Migration(
        version=5,
        name="005_phase12_deployments",
        up_sql="""
        CREATE TABLE IF NOT EXISTS deployments (
            deployment_id TEXT PRIMARY KEY,
            version TEXT NOT NULL,
            commit_sha TEXT NOT NULL,
            model_version TEXT NOT NULL,
            environment TEXT NOT NULL CHECK (environment IN ('development', 'testing', 'staging', 'production')),
            operator TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('PENDING', 'RUNNING', 'HEALTHY', 'DEGRADED', 'FAILED', 'ROLLED_BACK')),
            started_at TEXT NOT NULL,
            completed_at TEXT,
            duration_seconds REAL,
            health_check_summary_json TEXT,
            notes TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_deploy_env_time ON deployments (environment, started_at);

        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL,
            checksum TEXT NOT NULL
        );
        """,
        down_sql="""
        DROP TABLE IF EXISTS deployments;
        """
    ),
]


class MigrationManager:
    """Manages versioned database migrations with automatic pre-migration backup."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path).resolve()
        self.backup_dir = self.db_path.parent / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA foreign_keys = OFF;")
        return conn

    def _ensure_migration_table(self, conn: sqlite3.Connection) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL,
                checksum TEXT NOT NULL
            );
        """)
        conn.commit()

    def get_applied_versions(self) -> List[int]:
        if not self.db_path.exists():
            return []
        conn = self._get_connection()
        try:
            self._ensure_migration_table(conn)
            cur = conn.execute("SELECT version FROM schema_migrations ORDER BY version ASC;")
            return [row["version"] for row in cur.fetchall()]
        finally:
            conn.close()

    def backup(self, tag: str = "pre_migration") -> Path:
        """Creates a snapshot copy of the database before making schema alterations."""
        if not self.db_path.exists():
            return Path("")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"{self.db_path.stem}_{tag}_{timestamp}.sqlite3.bak"
        
        # Safe SQLite online backup
        src_conn = self._get_connection()
        try:
            dst_conn = sqlite3.connect(str(backup_file))
            with dst_conn:
                src_conn.backup(dst_conn)
            dst_conn.close()
        finally:
            src_conn.close()
            
        return backup_file

    def migrate(self, target_version: Optional[int] = None) -> List[Tuple[int, str]]:
        """Applies pending migrations up to target_version in order."""
        applied = set(self.get_applied_versions())
        pending = [m for m in MIGRATIONS if m.version not in applied]
        if target_version is not None:
            pending = [m for m in pending if m.version <= target_version]

        if not pending:
            return []

        # Create safety backup before applying migrations
        self.backup(tag=f"v{pending[0].version}_start")

        executed = []
        conn = self._get_connection()
        try:
            self._ensure_migration_table(conn)
            for m in pending:
                checksum = hashlib.sha256(m.up_sql.encode("utf-8")).hexdigest()
                with conn:
                    conn.executescript(m.up_sql)
                    now_str = datetime.now(timezone.utc).isoformat()
                    conn.execute(
                        "INSERT INTO schema_migrations (version, name, applied_at, checksum) VALUES (?, ?, ?, ?);",
                        (m.version, m.name, now_str, checksum)
                    )
                executed.append((m.version, m.name))
        finally:
            conn.close()

        return executed

    def rollback(self, target_version: int) -> List[Tuple[int, str]]:
        """Rolls back applied migrations down to target_version (exclusive)."""
        applied_versions = self.get_applied_versions()
        to_rollback = [
            m for m in reversed(MIGRATIONS)
            if m.version in applied_versions and m.version > target_version
        ]

        if not to_rollback:
            return []

        self.backup(tag=f"rollback_to_v{target_version}")

        rolled_back = []
        conn = self._get_connection()
        try:
            self._ensure_migration_table(conn)
            for m in to_rollback:
                with conn:
                    conn.executescript(m.down_sql)
                    conn.execute("DELETE FROM schema_migrations WHERE version = ?;", (m.version,))
                rolled_back.append((m.version, m.name))
        finally:
            conn.close()

        return rolled_back

    def status(self) -> List[Dict[str, Any]]:
        """Returns the migration status table."""
        applied_map = {}
        if self.db_path.exists():
            conn = self._get_connection()
            try:
                self._ensure_migration_table(conn)
                cur = conn.execute("SELECT version, name, applied_at, checksum FROM schema_migrations;")
                for row in cur.fetchall():
                    applied_map[row["version"]] = dict(row)
            finally:
                conn.close()

        results = []
        for m in MIGRATIONS:
            is_applied = m.version in applied_map
            info = applied_map.get(m.version, {})
            results.append({
                "version": m.version,
                "name": m.name,
                "applied": is_applied,
                "applied_at": info.get("applied_at"),
                "checksum": info.get("checksum"),
            })
        return results


def run_migrations_cli():
    import sys
    from config.deployment_config import get_deployment_config

    cfg = get_deployment_config()
    manager = MigrationManager(cfg.db_path)
    
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "migrate":
        target = int(sys.argv[2]) if len(sys.argv) > 2 else None
        print(f"[*] Running database migrations for {cfg.db_path}...")
        done = manager.migrate(target)
        if done:
            for v, n in done:
                print(f"  [✓] Applied migration v{v}: {n}")
        else:
            print("  [-] No pending migrations. Schema is up to date.")
    elif cmd == "rollback":
        if len(sys.argv) < 3:
            print("[!] Error: Specify target version to rollback to. Usage: python -m db.migrations rollback <target_version>")
            sys.exit(1)
        target = int(sys.argv[2])
        print(f"[*] Rolling back migrations to version {target}...")
        done = manager.rollback(target)
        for v, n in done:
            print(f"  [✓] Reverted migration v{v}: {n}")
    elif cmd == "status":
        print(f"=== Database Migration Status: {cfg.db_path} ===")
        for s in manager.status():
            status_tag = f"APPLIED ({s['applied_at']})" if s['applied'] else "PENDING"
            print(f"  [{'X' if s['applied'] else ' '}] v{s['version']} {s['name']:<25} : {status_tag}")
    else:
        print(f"Unknown command: {cmd}. Supported: migrate, rollback, status")


if __name__ == "__main__":
    run_migrations_cli()

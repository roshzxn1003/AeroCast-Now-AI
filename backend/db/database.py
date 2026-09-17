"""
Database Connection & Transaction Manager for AeroCast-Now AI.
Uses SQLite with Write-Ahead Logging (WAL) for high concurrency and zero data loss.
"""
import sqlite3
import os
import threading
from typing import Optional, List, Dict, Any
from pathlib import Path
from .schema import SCHEMA_SQL

DEFAULT_DB_PATH = os.getenv(
    "AEROCAST_DB_PATH",
    str(Path(__file__).parent.parent / "data" / "aerocast.sqlite3")
)

class DatabaseManager:
    _instance: Optional["DatabaseManager"] = None
    _lock = threading.Lock()

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        # Ensure parent directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    @classmethod
    def get_instance(cls, db_path: str = DEFAULT_DB_PATH) -> "DatabaseManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(db_path)
            return cls._instance

    def _get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            # Enable WAL mode for high concurrency
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA foreign_keys = ON;")
            self._local.conn = conn
        return self._local.conn

    def _migrate_db(self, conn: sqlite3.Connection):
        """Migrates legacy tables to updated constraints if needed."""
        try:
            cur = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='model_registry'")
            row = cur.fetchone()
            if row and row[0] and "CANDIDATE" not in row[0]:
                conn.execute("PRAGMA foreign_keys = OFF;")
                conn.execute("""
                    CREATE TABLE model_registry_new (
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
                """)
                conn.execute("INSERT INTO model_registry_new SELECT * FROM model_registry;")
                conn.execute("DROP TABLE model_registry;")
                conn.execute("ALTER TABLE model_registry_new RENAME TO model_registry;")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_model_stage ON model_registry (stage);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_model_prod ON model_registry (is_active_production);")
                conn.execute("PRAGMA foreign_keys = ON;")
        except Exception:
            pass

    def _init_db(self):
        conn = self._get_connection()
        with conn:
            conn.executescript(SCHEMA_SQL)
            self._migrate_db(conn)

    def execute(self, sql: str, params: tuple = ()) -> int:
        """Executes INSERT/UPDATE/DELETE and returns lastrowid or rowcount."""
        conn = self._get_connection()
        with conn:
            cur = conn.execute(sql, params)
            return cur.lastrowid or cur.rowcount

    def executemany(self, sql: str, seq_of_params: List[tuple]) -> int:
        conn = self._get_connection()
        with conn:
            cur = conn.executemany(sql, seq_of_params)
            return cur.rowcount

    def fetch_one(self, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cur = conn.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None

    def fetch_all(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cur = conn.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]

    def close(self):
        if hasattr(self._local, "conn") and self._local.conn is not None:
            self._local.conn.close()
            self._local.conn = None

def get_db() -> DatabaseManager:
    return DatabaseManager.get_instance()

db_manager = get_db()


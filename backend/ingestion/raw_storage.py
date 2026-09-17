"""
Raw Data Preservation, Storage & Idempotent Deduplication Engine.
Phase 9 Operational Data Infrastructure.

Stores authentic untouched raw provider payloads in partition-indexed storage:
  data/raw/<domain>/<YYYY>/<MM>/<DD>/<provider_id>_<timestamp>_<hash[:8]>.<ext>
Computes cryptographic SHA-256 hashes, guarantees idempotent insertion,
and records all transactions into the raw_ingestion_log table.
"""
from __future__ import annotations

import os
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple, Union

from db.database import db_manager
from core.canonical_observation import CanonicalObservation

logger = logging.getLogger("aerocast.ingestion.raw_storage")

DEFAULT_RAW_DIR = Path(__file__).parent.parent / "data" / "raw"

class RawDataStorage:
    """
    Manages raw observation artifact persistence and cryptographic deduplication.
    """

    def __init__(self, base_dir: Union[str, Path] = DEFAULT_RAW_DIR):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def store_raw_payload(
        self,
        domain: str,
        provider_id: str,
        dataset: str,
        payload: Union[bytes, str, Dict[str, Any]],
        observation_time: Optional[str] = None,
        extension: str = "json",
    ) -> Dict[str, Any]:
        """
        Idempotently persists raw payload to disk and tracks in raw_ingestion_log.
        Returns metadata dict containing file_hash, file_path, status (STORED or DUPLICATE).
        """
        now = datetime.now(timezone.utc)
        now_utc = now.isoformat()
        obs_time = observation_time or now_utc

        # 1. Normalize payload to bytes
        if isinstance(payload, bytes):
            raw_bytes = payload
        elif isinstance(payload, str):
            raw_bytes = payload.encode("utf-8")
        elif isinstance(payload, dict):
            raw_bytes = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        else:
            raw_bytes = str(payload).encode("utf-8")

        # 2. Compute SHA-256 hash
        file_hash = hashlib.sha256(raw_bytes).hexdigest()
        file_size = len(raw_bytes)

        # 3. Check for existing hash in raw_ingestion_log (Deduplication)
        existing = db_manager.fetch_one(
            "SELECT ingestion_id, file_path, status, ingested_at FROM raw_ingestion_log WHERE file_hash = ?",
            (file_hash,),
        )
        if existing:
            logger.debug(
                "DUPLICATE PAYLOAD: Hash %s already stored at %s on %s. Skipping write.",
                file_hash[:12],
                existing["file_path"],
                existing["ingested_at"],
            )
            return {
                "ingestion_id": existing["ingestion_id"],
                "file_path": existing["file_path"],
                "file_hash": file_hash,
                "file_size_bytes": file_size,
                "status": "DUPLICATE",
                "is_duplicate": True,
            }

        # 4. Generate partition directory: data/raw/<domain>/<YYYY>/<MM>/<DD>/
        year_str = now.strftime("%Y")
        month_str = now.strftime("%m")
        day_str = now.strftime("%d")
        time_slug = now.strftime("%H%M%S")

        target_dir = self.base_dir / domain.lower() / year_str / month_str / day_str
        target_dir.mkdir(parents=True, exist_ok=True)

        clean_ext = extension.lstrip(".")
        filename = f"{provider_id.lower()}_{time_slug}_{file_hash[:8]}.{clean_ext}"
        target_file = target_dir / filename

        # 5. Write raw file to disk
        try:
            with open(target_file, "wb") as f:
                f.write(raw_bytes)
        except Exception as e:
            logger.error("Failed to write raw payload to %s: %s", target_file, e)
            raise

        # 6. Record into raw_ingestion_log
        ingestion_id = f"RAW-{now.strftime('%Y%m%d')}-{file_hash[:10].upper()}"
        try:
            db_manager.execute(
                """
                INSERT INTO raw_ingestion_log (
                    ingestion_id, source_provider, dataset, file_path,
                    file_hash, file_size_bytes, ingested_at, observation_time,
                    status, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ingestion_id,
                    provider_id,
                    dataset,
                    str(target_file),
                    file_hash,
                    file_size,
                    now_utc,
                    obs_time,
                    "STORED",
                    None,
                ),
            )
        except Exception as e:
            logger.warning("Could not insert into raw_ingestion_log: %s", e)

        return {
            "ingestion_id": ingestion_id,
            "file_path": str(target_file),
            "file_hash": file_hash,
            "file_size_bytes": file_size,
            "status": "STORED",
            "is_duplicate": False,
        }

    def persist_canonical_observation(self, obs: CanonicalObservation) -> bool:
        """
        Persists a normalized CanonicalObservation into the relational observations table idempotently.
        """
        try:
            # Check if already exists
            existing = db_manager.fetch_one(
                "SELECT id FROM observations WHERE obs_id = ?",
                (obs.observation_id,),
            )
            if existing:
                return False

            payload = obs.to_dict()
            lat = getattr(obs, "latitude", None)
            lon = getattr(obs, "longitude", None)
            val_num = getattr(obs, "value", None)
            bbox = None
            if hasattr(obs, "domain") and obs.domain:
                bbox = f"{obs.domain.lat_min},{obs.domain.lon_min},{obs.domain.lat_max},{obs.domain.lon_max}"

            db_manager.execute(
                """
                INSERT INTO observations (
                    obs_id, source, dataset, observation_time, ingested_at,
                    latitude, longitude, coverage_bbox, variable, unit,
                    value_numeric, payload_json, quality_status, quality_reason,
                    processing_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    obs.observation_id,
                    obs.source,
                    obs.dataset,
                    obs.timestamp,
                    obs.ingestion_time,
                    lat,
                    lon,
                    bbox,
                    obs.variable,
                    obs.unit,
                    val_num,
                    json.dumps(payload, default=str),
                    obs.quality_flag.value,
                    obs.quality_reason,
                    "v2.0-phase9",
                ),
            )
            return True
        except Exception as e:
            logger.warning("Failed to persist canonical observation %s: %s", obs.observation_id, e)
            return False

raw_storage = RawDataStorage()

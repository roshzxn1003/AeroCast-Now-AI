"""
Prediction Provenance & Storage Engine.
Phase 10 Operational Platform — Guarantees Traceability of Every Issued Forecast.
"""
from __future__ import annotations

import uuid
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from db.database import get_db

@dataclass
class PredictionRecord:
    prediction_id: str
    model_id: str
    model_version: str
    model_hash: str
    station: str
    generated_at: str
    valid_time: str
    lead_time_min: int
    max_dbz: float
    max_vil: float
    has_jump: bool
    storm_count: int
    input_timestamps: List[str]
    data_sources: List[str]
    prediction_summary: Dict[str, Any]
    region: str = "Tamil Nadu"
    grid_definition: str = "32x32@4km EPSG:4326"
    input_dataset_version: str = "2026.09.001"
    feature_version: str = "1.0.0"
    confidence_score: Optional[float] = None
    inference_status: str = "COMPLETED"
    initialization_time: Optional[str] = None

    def __post_init__(self):
        if not self.initialization_time:
            self.initialization_time = self.generated_at

    def save(self):
        """Persists immutable prediction record into SQLite."""
        db = get_db()
        payload = dict(self.prediction_summary)
        payload["region"] = self.region
        payload["grid_definition"] = self.grid_definition
        payload["input_dataset_version"] = self.input_dataset_version
        payload["feature_version"] = self.feature_version
        payload["confidence_score"] = self.confidence_score
        payload["inference_status"] = self.inference_status
        payload["initialization_time"] = self.initialization_time

        db.execute(
            """
            INSERT OR REPLACE INTO predictions (
                prediction_id, model_id, model_version, model_hash, station,
                generated_at, valid_time, lead_time_min, max_dbz, max_vil,
                has_jump, storm_count, input_timestamps_json, data_sources_json,
                prediction_payload_json, verified
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                self.prediction_id,
                self.model_id,
                self.model_version,
                self.model_hash,
                self.station,
                self.generated_at,
                self.valid_time,
                self.lead_time_min,
                self.max_dbz,
                self.max_vil,
                1 if self.has_jump else 0,
                self.storm_count,
                json.dumps(self.input_timestamps),
                json.dumps(self.data_sources),
                json.dumps(payload),
            ),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def record_prediction(
    model_id: str,
    model_version: str,
    model_hash: str,
    station: str,
    generated_at: str,
    valid_time: str,
    lead_time_min: int,
    max_dbz: float,
    max_vil: float,
    has_jump: bool,
    storm_count: int,
    input_timestamps: List[str],
    data_sources: List[str],
    prediction_summary: Dict[str, Any],
    region: str = "Tamil Nadu",
    grid_definition: str = "32x32@4km EPSG:4326",
    confidence_score: Optional[float] = None,
    inference_status: str = "COMPLETED",
) -> str:
    """Convenience helper to record and store forecast prediction provenance."""
    pred_id = f"PRED-{uuid.uuid4().hex[:12].upper()}"
    rec = PredictionRecord(
        prediction_id=pred_id,
        model_id=model_id,
        model_version=model_version,
        model_hash=model_hash,
        station=station,
        generated_at=generated_at,
        valid_time=valid_time,
        lead_time_min=lead_time_min,
        max_dbz=round(float(max_dbz), 2),
        max_vil=round(float(max_vil), 2),
        has_jump=has_jump,
        storm_count=storm_count,
        input_timestamps=input_timestamps,
        data_sources=data_sources,
        prediction_summary=prediction_summary,
        region=region,
        grid_definition=grid_definition,
        confidence_score=confidence_score,
        inference_status=inference_status,
        initialization_time=generated_at,
    )
    rec.save()
    return pred_id

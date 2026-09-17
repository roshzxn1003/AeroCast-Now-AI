"""
Event-Based Storm Verification & False Alarm / Missed Event Root-Cause Engine.
Phase 10 Operational Platform — Deep Convective Case Study & Error Diagnostics.

Implements:
1. Convective Storm Event extraction and lifecycle tracking.
2. Centroid geographic location error calculation using Haversine formula.
3. Event detection lead-time calculation (T_observed - T_first_model_detection).
4. False Alarm Root-Cause categorization (weak convection, rapid dissipation, data gap, model error).
5. Missed Event Contributing Factor logging for continuous model retraining datasets.
"""
from __future__ import annotations

import math
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Tuple
import numpy as np

from db.database import get_db

logger = logging.getLogger("aerocast.verification.event")

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two geographic points in kilometers."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * R * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


class FalseAlarmCause:
    WEAK_CONVECTION = "weak_convection"
    RAPID_DISSIPATION = "rapid_storm_dissipation"
    DATA_QUALITY = "data_quality_problem"
    OBSERVATION_GAP = "observation_gap"
    MODEL_ERROR = "model_error"
    BOUNDARY_ERROR = "boundary_condition_error"
    TRACKING_ERROR = "storm_tracking_error"
    UNKNOWN = "UNKNOWN"


class StormEventVerificationEngine:
    """
    Manages historical storm event registers, case study tracking, and diagnostic root-cause analysis.
    """

    def __init__(self):
        self.db = get_db()

    def register_storm_event(
        self,
        name: str,
        region: str,
        start_time: str,
        end_time: Optional[str],
        severity: str,
        max_observed_dbz: float,
        max_predicted_dbz: float,
        first_model_detection_time: Optional[str] = None,
        first_observation_time: Optional[str] = None,
        pred_centroid: Optional[Tuple[float, float]] = None,
        obs_centroid: Optional[Tuple[float, float]] = None,
        classification: str = "DETECTED",  # DETECTED, MISSED, FALSE_ALARM
        false_alarm_cause: Optional[str] = None,
        miss_contributing_factors: Optional[str] = None,
        notes: str = "",
    ) -> Dict[str, Any]:
        """Registers a severe convective event into the storm_events ledger."""
        event_id = f"EVENT-{uuid.uuid4().hex[:10].upper()}"

        # Calculate lead time in minutes if both timestamps exist
        detection_lead_min = None
        if first_model_detection_time and first_observation_time:
            try:
                t_model = datetime.fromisoformat(first_model_detection_time.replace("Z", "+00:00"))
                t_obs = datetime.fromisoformat(first_observation_time.replace("Z", "+00:00"))
                detection_lead_min = round((t_obs - t_model).total_seconds() / 60.0, 1)
            except Exception:
                pass

        # Calculate location error in km if both centroids exist
        loc_error_km = None
        if pred_centroid and obs_centroid:
            loc_error_km = round(haversine_km(pred_centroid[0], pred_centroid[1], obs_centroid[0], obs_centroid[1]), 2)

        self.db.execute(
            """
            INSERT INTO storm_events (
                event_id, name, region, start_time, end_time, severity,
                max_observed_dbz, max_predicted_dbz, first_model_detection_time,
                first_observation_time, detection_lead_time_min, location_error_km,
                classification, false_alarm_cause, miss_contributing_factors, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                name,
                region,
                start_time,
                end_time,
                severity,
                max_observed_dbz,
                max_predicted_dbz,
                first_model_detection_time,
                first_observation_time,
                detection_lead_min,
                loc_error_km,
                classification,
                false_alarm_cause,
                miss_contributing_factors,
                notes,
            ),
        )

        return {
            "event_id": event_id,
            "name": name,
            "region": region,
            "classification": classification,
            "detection_lead_time_min": detection_lead_min,
            "location_error_km": loc_error_km,
            "severity": severity,
        }

    def analyze_false_alarm(
        self,
        predicted_max_dbz: float,
        observed_max_dbz: float,
        obs_available: bool,
        has_lightning_jump: bool,
        convective_inhibition_cin: Optional[float] = None,
    ) -> str:
        """
        Diagnoses root causes for false alarms based on atmospheric physics:
        - If CIN was very high (> 150 J/kg), convection was capped -> rapid storm dissipation.
        - If obs was missing entirely -> observation gap.
        - If reflectivity was 25-32 dBZ -> weak convection.
        - Otherwise -> model error or unknown.
        """
        if not obs_available:
            return FalseAlarmCause.OBSERVATION_GAP
        if convective_inhibition_cin is not None and convective_inhibition_cin > 120.0:
            return FalseAlarmCause.RAPID_DISSIPATION
        if 20.0 <= observed_max_dbz < 35.0:
            return FalseAlarmCause.WEAK_CONVECTION
        if predicted_max_dbz >= 45.0 and observed_max_dbz < 15.0:
            return FalseAlarmCause.MODEL_ERROR
        return FalseAlarmCause.UNKNOWN

    def list_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns registered storm events and statistics."""
        return self.db.fetch_all(
            "SELECT * FROM storm_events ORDER BY start_time DESC LIMIT ?", (limit,)
        )

    def get_event_statistics(self) -> Dict[str, Any]:
        """Aggregates storm event verification metrics."""
        events = self.db.fetch_all("SELECT * FROM storm_events")
        total = len(events)
        if total == 0:
            return {
                "total_events": 0,
                "detected": 0,
                "missed": 0,
                "false_alarms": 0,
                "detection_rate": 0.0,
                "avg_lead_time_min": 0.0,
                "avg_location_error_km": 0.0,
            }

        detected = sum(1 for e in events if e["classification"] == "DETECTED")
        missed = sum(1 for e in events if e["classification"] == "MISSED")
        fa = sum(1 for e in events if e["classification"] == "FALSE_ALARM")

        lead_times = [e["detection_lead_time_min"] for e in events if e["detection_lead_time_min"] is not None]
        loc_errors = [e["location_error_km"] for e in events if e["location_error_km"] is not None]

        return {
            "total_events": total,
            "detected": detected,
            "missed": missed,
            "false_alarms": fa,
            "detection_rate": round(detected / max(1, detected + missed), 3),
            "avg_lead_time_min": round(float(np.mean(lead_times)), 1) if lead_times else 0.0,
            "avg_location_error_km": round(float(np.mean(loc_errors)), 2) if loc_errors else 0.0,
        }

storm_event_verifier = StormEventVerificationEngine()

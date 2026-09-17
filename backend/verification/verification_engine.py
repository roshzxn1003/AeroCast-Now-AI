"""
Automated Forecast Verification Pipeline.
Phase 8 Operational Platform — Closes the Scientific Loop by Comparing Predictions with Real Truth.
"""
import math
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from db.database import get_db

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two geographic coordinates in kilometers."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * R * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

class ForecastVerificationEngine:
    """Matches mature forecast predictions against actual observed atmospheric truth."""

    def __init__(self):
        self.db = get_db()

    def find_pending_verifications(
        self,
        current_time_iso: Optional[str] = None,
        tolerance_minutes: int = 15,
    ) -> List[Dict[str, Any]]:
        """
        Finds stored predictions whose valid_time has passed and are not yet verified.
        """
        if current_time_iso is None:
            current_time_iso = datetime.now(timezone.utc).isoformat()

        # Query unverified predictions where valid_time <= current_time
        return self.db.fetch_all(
            """
            SELECT * FROM predictions
            WHERE verified = 0 AND valid_time <= ?
            ORDER BY valid_time ASC LIMIT 50
            """,
            (current_time_iso,),
        )

    def verify_prediction(
        self,
        prediction_id: str,
        observed_max_dbz: float,
        observed_centroid_lat: Optional[float] = None,
        observed_centroid_lon: Optional[float] = None,
        predicted_centroid_lat: Optional[float] = None,
        predicted_centroid_lon: Optional[float] = None,
        threshold_dbz: float = 35.0,
        notes: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        Compares prediction against observed truth, computes contingency scores and errors,
        and saves the verification record.
        """
        pred = self.db.fetch_one(
            "SELECT * FROM predictions WHERE prediction_id = ?", (prediction_id,)
        )
        if not pred:
            return None

        pred_max_dbz = pred["max_dbz"]
        dbz_error = round(pred_max_dbz - observed_max_dbz, 2)

        # Categorical contingency classification at convective threshold
        is_pred_storm = pred_max_dbz >= threshold_dbz
        is_obs_storm = observed_max_dbz >= threshold_dbz

        hit = 1 if (is_pred_storm and is_obs_storm) else 0
        miss = 1 if (not is_pred_storm and is_obs_storm) else 0
        false_alarm = 1 if (is_pred_storm and not is_obs_storm) else 0
        correct_neg = 1 if (not is_pred_storm and not is_obs_storm) else 0

        # Location displacement error in kilometers
        location_error_km = None
        if (
            observed_centroid_lat is not None
            and observed_centroid_lon is not None
            and predicted_centroid_lat is not None
            and predicted_centroid_lon is not None
        ):
            location_error_km = round(
                haversine_km(
                    predicted_centroid_lat,
                    predicted_centroid_lon,
                    observed_centroid_lat,
                    observed_centroid_lon,
                ),
                2,
            )

        verif_id = f"VERIF-{uuid.uuid4().hex[:12].upper()}"
        now = datetime.now(timezone.utc).isoformat()

        self.db.execute(
            """
            INSERT INTO verifications (
                verification_id, prediction_id, verified_at, lead_time_min,
                observed_max_dbz, predicted_max_dbz, dbz_error,
                hit, miss, false_alarm, correct_negative,
                location_error_km, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                verif_id,
                prediction_id,
                now,
                pred["lead_time_min"],
                observed_max_dbz,
                pred_max_dbz,
                dbz_error,
                hit,
                miss,
                false_alarm,
                correct_neg,
                location_error_km,
                notes,
            ),
        )

        # Mark prediction as verified
        self.db.execute(
            "UPDATE predictions SET verified = 1 WHERE prediction_id = ?",
            (prediction_id,),
        )

        return {
            "verification_id": verif_id,
            "prediction_id": prediction_id,
            "lead_time_min": pred["lead_time_min"],
            "predicted_max_dbz": pred_max_dbz,
            "observed_max_dbz": observed_max_dbz,
            "dbz_error": dbz_error,
            "classification": "HIT" if hit else "MISS" if miss else "FALSE_ALARM" if false_alarm else "CORRECT_NEGATIVE",
            "location_error_km": location_error_km,
        }

    def get_summary_statistics(self) -> Dict[str, Any]:
        """Calculates global verification scores (CSI, POD, FAR, HSS, MAE)."""
        rows = self.db.fetch_all("SELECT * FROM verifications")
        if not rows:
            return {
                "total_verified": 0,
                "csi": 0.0,
                "pod": 0.0,
                "far": 0.0,
                "hss": 0.0,
                "mean_absolute_error_dbz": 0.0,
                "status": "NO_VERIFICATIONS_YET",
            }

        hits = sum(r["hit"] for r in rows)
        misses = sum(r["miss"] for r in rows)
        fas = sum(r["false_alarm"] for r in rows)
        cns = sum(r["correct_negative"] for r in rows)
        errors = [abs(r["dbz_error"]) for r in rows if r["dbz_error"] is not None]

        # WMO Standard Verification Metrics
        csi = hits / (hits + misses + fas) if (hits + misses + fas) > 0 else 0.0
        pod = hits / (hits + misses) if (hits + misses) > 0 else 0.0
        far = fas / (hits + fas) if (hits + fas) > 0 else 0.0

        n = hits + misses + fas + cns
        expected = ((hits + misses) * (hits + fas) + (cns + misses) * (cns + fas)) / n if n > 0 else 0.0
        hss = (2 * (hits * cns - misses * fas)) / ((hits + misses) * (misses + cns) + (hits + fas) * (fas + cns)) if ((hits + misses) * (misses + cns) + (hits + fas) * (fas + cns)) > 0 else 0.0

        mae = sum(errors) / len(errors) if errors else 0.0

        return {
            "total_verified": len(rows),
            "hits": hits,
            "misses": misses,
            "false_alarms": fas,
            "correct_negatives": cns,
            "csi": round(csi, 4),
            "pod": round(pod, 4),
            "far": round(far, 4),
            "hss": round(hss, 4),
            "mean_absolute_error_dbz": round(mae, 2),
        }

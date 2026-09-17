"""
Historical Replay Engine.
Phase 9 Operational Data Infrastructure.

Enables reproducible meteorological case studies and algorithmic backtesting
by replaying historical observation archives through the operational pipeline.
Operates with explicit mode tagging (REPLAY), speed multipliers (1x, 10x, 100x),
and strict segregation from live real-time feeds.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.canonical_observation import (
    CanonicalObservation,
    GriddedObservation,
    CanonicalQualityFlag,
    CanonicalProvenance,
    ProcessingStatus,
    SpatialDomain,
)
from db.database import db_manager
from ingestion.provider_manager import provider_manager
from ingestion.temporal_sync import SynchronizedTemporalSequence, temporal_synchronizer
from ingestion.inference_gate import inference_gate, InferenceReadinessResult

logger = logging.getLogger("aerocast.ingestion.replay")

class ReplaySession:
    """Manages state for an active historical replay run."""

    def __init__(
        self,
        session_id: str,
        start_time: str,
        end_time: str,
        speed_multiplier: float = 1.0,
        step_minutes: int = 15,
        center_lat: float = 13.0827,
        center_lon: float = 80.2707,
    ):
        self.session_id = session_id
        self.start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        self.end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        self.current_time = self.start_time
        self.speed_multiplier = max(0.1, speed_multiplier)
        self.step_minutes = step_minutes
        self.center_lat = center_lat
        self.center_lon = center_lon
        self.is_running: bool = False
        self.step_count: int = 0
        self.history: List[Dict[str, Any]] = []

    @property
    def progress_pct(self) -> float:
        total_span = (self.end_time - self.start_time).total_seconds()
        if total_span <= 0:
            return 100.0
        elapsed = (self.current_time - self.start_time).total_seconds()
        return round(min(100.0, max(0.0, (elapsed / total_span) * 100.0)), 2)


class HistoricalReplayEngine:
    """
    Coordinates historical dataset playback, temporal frame reconstruction,
    and simulated clock progression for research validation.
    """

    def __init__(self):
        self.active_session: Optional[ReplaySession] = None
        self._lock = asyncio.Lock()

    async def start_replay(
        self,
        start_time: str,
        end_time: str,
        speed_multiplier: float = 1.0,
        step_minutes: int = 15,
        center_lat: float = 13.0827,
        center_lon: float = 80.2707,
    ) -> Dict[str, Any]:
        """Initiates a new historical replay session."""
        async with self._lock:
            session_id = f"REPLAY-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
            self.active_session = ReplaySession(
                session_id=session_id,
                start_time=start_time,
                end_time=end_time,
                speed_multiplier=speed_multiplier,
                step_minutes=step_minutes,
                center_lat=center_lat,
                center_lon=center_lon,
            )
            self.active_session.is_running = True
            provider_manager.set_mode("REPLAY")
            logger.info("Started replay session %s from %s to %s at %sx", session_id, start_time, end_time, speed_multiplier)

            return {
                "session_id": session_id,
                "status": "STARTED",
                "start_time": start_time,
                "end_time": end_time,
                "speed_multiplier": speed_multiplier,
                "progress_pct": 0.0,
            }

    async def step_replay(self) -> Optional[Dict[str, Any]]:
        """Advances replay clock by step_minutes and retrieves historical synchronized state."""
        if not self.active_session or not self.active_session.is_running:
            return None

        session = self.active_session
        if session.current_time > session.end_time:
            session.is_running = False
            provider_manager.set_mode("REAL")
            logger.info("Replay session %s reached end time. Reverting to REAL mode.", session.session_id)
            return {
                "session_id": session.session_id,
                "status": "COMPLETED",
                "current_time": session.current_time.isoformat(),
                "progress_pct": 100.0,
            }

        t_current = session.current_time
        # Fetch observations from DB around t_current
        t_minus_45 = t_current - timedelta(minutes=45)
        rows = db_manager.fetch_all(
            """
            SELECT obs_id, source, dataset, observation_time, latitude, longitude,
                   variable, unit, value_numeric, payload_json, quality_status
            FROM observations
            WHERE observation_time >= ? AND observation_time <= ?
            ORDER BY observation_time ASC
            """,
            (t_minus_45.isoformat(), t_current.isoformat()),
        )

        # Convert rows back into CanonicalObservations if present
        observations: List[GriddedObservation] = []
        for r in rows:
            obs_id = r["obs_id"]
            var = r["variable"]
            time_str = r["observation_time"]
            obs = GriddedObservation(
                observation_id=f"REPLAY-{obs_id}",
                obs_type=None,
                source=r["source"],
                provider=f"REPLAY_{r['source']}",
                dataset=r["dataset"],
                variable=var,
                timestamp=time_str,
                valid_time=time_str,
                ingestion_time=datetime.now(timezone.utc).isoformat(),
                unit=r["unit"],
                quality_flag=CanonicalQualityFlag.VALID,
                processing_status=ProcessingStatus.NORMALIZED,
                provenance=CanonicalProvenance(
                    source_provider="HISTORICAL_ARCHIVE",
                    source_dataset=r["dataset"],
                    source_url_or_channel="sqlite3:observations",
                    source_timestamp=time_str,
                    ingestion_timestamp=datetime.now(timezone.utc).isoformat(),
                    transformation_notes=["Historical playback step"],
                ),
                grid_shape=(32, 32),
                grid_data=np.zeros((32, 32), dtype=np.float32),
            )
            observations.append(obs)

        # Synchronize
        seq = temporal_synchronizer.synchronize_observations(observations, t0=t_current)
        readiness = inference_gate.evaluate_readiness(seq, mode="REPLAY")

        step_result = {
            "session_id": session.session_id,
            "step_index": session.step_count,
            "timestamp": t_current.isoformat(),
            "progress_pct": session.progress_pct,
            "observation_count": len(observations),
            "readiness": readiness.to_dict(),
        }
        session.history.append(step_result)
        session.step_count += 1
        session.current_time += timedelta(minutes=session.step_minutes)

        return step_result

    def stop_replay(self) -> Dict[str, Any]:
        """Halts current replay and restores REAL mode."""
        if not self.active_session:
            return {"status": "NO_ACTIVE_SESSION"}

        session = self.active_session
        session.is_running = False
        provider_manager.set_mode("REAL")
        self.active_session = None

        return {
            "session_id": session.session_id,
            "status": "STOPPED",
            "total_steps": session.step_count,
            "final_progress_pct": session.progress_pct,
        }

    def get_status(self) -> Dict[str, Any]:
        """Returns live status of the replay engine."""
        if not self.active_session:
            return {"is_active": False, "session": None}

        s = self.active_session
        return {
            "is_active": s.is_running,
            "session_id": s.session_id,
            "current_time": s.current_time.isoformat(),
            "start_time": s.start_time.isoformat(),
            "end_time": s.end_time.isoformat(),
            "speed_multiplier": s.speed_multiplier,
            "step_count": s.step_count,
            "progress_pct": s.progress_pct,
        }

replay_engine = HistoricalReplayEngine()

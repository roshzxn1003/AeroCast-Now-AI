"""
Atmospheric Data Freshness Tracker
==================================
Monitors and reports operational data latency across all multi-modal feeds:
  - Doppler Radar (scan cycle ~10-15 min)
  - Satellite TIR (scan cycle ~15-30 min)
  - Lightning Detection (low latency < 2 min)
  - Convective Sounding (model run 1-3 hrs)

Strict classification:
  - FRESH:   age <= 20 min
  - DELAYED: 20 < age <= 60 min
  - STALE:   age > 60 min
  - MISSING: stream offline or null
  - INVALID: out of physical bounds / corrupt
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("aerocast.live.freshness")

FRESH_LIMIT_MIN = 20.0
DELAYED_LIMIT_MIN = 60.0


@dataclass
class StreamFreshness:
    """Freshness status for an individual sensor feed."""
    stream_name: str
    status: str              # 'fresh', 'delayed', 'stale', 'missing', 'invalid'
    age_minutes: float
    timestamp: Optional[str] = None
    source: str = "UNKNOWN"
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stream_name": self.stream_name,
            "status": self.status,
            "age_minutes": round(self.age_minutes, 1),
            "timestamp": self.timestamp,
            "source": self.source,
            "latency_ms": round(self.latency_ms, 1),
        }


@dataclass
class PipelineFreshnessReport:
    """Consolidated freshness assessment across the entire nowcasting ingestion chain."""
    overall_status: str       # 'fresh', 'delayed', 'stale', 'unhealthy'
    checked_at: str
    streams: Dict[str, StreamFreshness] = field(default_factory=dict)
    summary_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_status": self.overall_status,
            "checked_at": self.checked_at,
            "streams": {k: v.to_dict() for k, v in self.streams.items()},
            "summary_message": self.summary_message,
        }


class FreshnessTracker:
    """
    Evaluates multi-modal observation streams and determines overall pipeline health.
    """

    def __init__(
        self,
        fresh_threshold_min: float = FRESH_LIMIT_MIN,
        delayed_threshold_min: float = DELAYED_LIMIT_MIN,
    ) -> None:
        self.fresh_threshold = fresh_threshold_min
        self.delayed_threshold = delayed_threshold_min

    def compute_stream_status(
        self,
        stream_name: str,
        obs_time: Optional[datetime],
        source: str = "UNKNOWN",
        latency_ms: float = 0.0,
        is_valid: bool = True,
    ) -> StreamFreshness:
        """
        Computes the freshness of a single observation stream.
        """
        if not is_valid:
            return StreamFreshness(
                stream_name=stream_name,
                status="invalid",
                age_minutes=9999.0,
                timestamp=obs_time.isoformat() if obs_time else None,
                source=source,
                latency_ms=latency_ms,
            )

        if obs_time is None:
            return StreamFreshness(
                stream_name=stream_name,
                status="missing",
                age_minutes=9999.0,
                timestamp=None,
                source=source,
                latency_ms=latency_ms,
            )

        now = datetime.now(timezone.utc)
        if obs_time.tzinfo is None:
            obs_time = obs_time.replace(tzinfo=timezone.utc)

        age_sec = max(0.0, (now - obs_time).total_seconds())
        age_min = age_sec / 60.0

        if age_min <= self.fresh_threshold:
            status = "fresh"
        elif age_min <= self.delayed_threshold:
            status = "delayed"
        else:
            status = "stale"

        return StreamFreshness(
            stream_name=stream_name,
            status=status,
            age_minutes=age_min,
            timestamp=obs_time.isoformat(),
            source=source,
            latency_ms=latency_ms,
        )

    def evaluate_pipeline(
        self,
        radar_res: Any,
        satellite_res: Any,
        lightning_res: Any,
        weather_res: Any,
    ) -> PipelineFreshnessReport:
        """
        Evaluates the aggregate health from all four providers.
        """
        streams: Dict[str, StreamFreshness] = {}

        # 1. Radar
        streams["radar"] = self.compute_stream_status(
            stream_name="radar",
            obs_time=getattr(radar_res, "timestamp", None),
            source=getattr(radar_res, "source", "UNKNOWN"),
            latency_ms=getattr(radar_res, "latency_ms", 0.0),
            is_valid=getattr(radar_res, "success", False),
        )

        # 2. Satellite
        streams["satellite"] = self.compute_stream_status(
            stream_name="satellite",
            obs_time=getattr(satellite_res, "timestamp", None),
            source=getattr(satellite_res, "source", "UNKNOWN"),
            latency_ms=getattr(satellite_res, "latency_ms", 0.0),
            is_valid=getattr(satellite_res, "success", False),
        )

        # 3. Lightning
        streams["lightning"] = self.compute_stream_status(
            stream_name="lightning",
            obs_time=getattr(lightning_res, "timestamp", None),
            source=getattr(lightning_res, "source", "UNKNOWN"),
            latency_ms=getattr(lightning_res, "latency_ms", 0.0),
            is_valid=getattr(lightning_res, "success", False),
        )

        # 4. Weather / Sounding
        streams["weather"] = self.compute_stream_status(
            stream_name="weather",
            obs_time=getattr(weather_res, "timestamp", None),
            source=getattr(weather_res, "source", "UNKNOWN"),
            latency_ms=getattr(weather_res, "latency_ms", 0.0),
            is_valid=getattr(weather_res, "success", False),
        )

        # Determine overall pipeline status
        statuses = [s.status for s in streams.values()]

        if all(s == "fresh" for s in statuses):
            overall = "fresh"
            msg = "All multi-modal observation feeds are fully fresh and within normal scan latency."
        elif any(s in ("missing", "invalid") for s in (streams["radar"].status, streams["satellite"].status)):
            overall = "unhealthy"
            msg = "Primary remote sensing feeds (radar or satellite) are missing or invalid."
        elif any(s == "stale" for s in statuses):
            overall = "stale"
            msg = "One or more feeds exceed 60-minute latency thresholds."
        elif any(s == "delayed" for s in statuses):
            overall = "delayed"
            msg = "Feeds are slightly delayed (20-60 minutes) but within operational tolerance."
        else:
            overall = "delayed"
            msg = "Operational hybrid data status."

        return PipelineFreshnessReport(
            overall_status=overall,
            checked_at=datetime.now(timezone.utc).isoformat(),
            streams=streams,
            summary_message=msg,
        )

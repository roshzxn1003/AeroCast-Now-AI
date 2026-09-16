"""
Base Observation Provider Interface
===================================
Defines the standard contract, result container, and validation routines
for all real-world atmospheric data providers:
  - Doppler Weather Radar (dBZ, VIL)
  - Geostationary Meteorological Satellite (INSAT-3D TIR)
  - Ground-based Lightning Detection Network (Blitzortung / LDN)
  - Numerical Convective Sounding / Weather Analysis (Open-Meteo / GFS)

Strictly enforces physical sanity checks, latency measurement, and freshness tracking.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("aerocast.providers.base")

# Freshness thresholds in minutes
FRESH_THRESHOLD_MIN = 20.0
DELAYED_THRESHOLD_MIN = 60.0


@dataclass
class ObservationQuality:
    """Scientific data quality and physical validity report."""
    valid: bool
    quality_score: float = 1.0       # 0.0 to 1.0
    issues: List[str] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)
    out_of_bounds: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "quality_score": round(self.quality_score, 3),
            "issues": self.issues,
            "missing_fields": self.missing_fields,
            "out_of_bounds": self.out_of_bounds,
        }


@dataclass
class ProviderResult:
    """
    Standard container returned by every observation provider.
    """
    success: bool
    data: Any
    timestamp: datetime
    latency_ms: float
    source: str
    freshness: str                   # 'fresh', 'delayed', 'stale', 'missing', 'invalid'
    age_minutes: float
    quality: ObservationQuality
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "timestamp": self.timestamp.isoformat(),
            "latency_ms": round(self.latency_ms, 1),
            "source": self.source,
            "freshness": self.freshness,
            "age_minutes": round(self.age_minutes, 1),
            "quality": self.quality.to_dict(),
            "error": self.error,
            "metadata": self.metadata,
        }


class BaseObservationProvider(ABC):
    """
    Abstract Base Class for atmospheric data providers.
    All providers must implement fetch_latest() and validate().
    """

    def __init__(self, name: str, source_type: str) -> None:
        self._name = name
        self._source_type = source_type

    @property
    def name(self) -> str:
        return self._name

    @property
    def source_type(self) -> str:
        return self._source_type

    @abstractmethod
    async def fetch_latest(self, lat: float, lon: float, **kwargs: Any) -> ProviderResult:
        """
        Asynchronously fetches and decodes the latest real observation.
        Must never throw unhandled exceptions; return a ProviderResult with success=False.
        """
        pass

    @abstractmethod
    def validate(self, data: Any) -> ObservationQuality:
        """
        Performs physical sanity and dimensional checks on raw/decoded data.
        """
        pass

    def get_freshness(self, obs_time: Optional[datetime]) -> Tuple[str, float]:
        """
        Evaluates data age against meteorological freshness standards.
          - Fresh: <= 20 min
          - Delayed: 20 < t <= 60 min
          - Stale: > 60 min
          - Missing: timestamp is None
        """
        if obs_time is None:
            return "missing", 9999.0

        now = datetime.now(timezone.utc)
        if obs_time.tzinfo is None:
            obs_time = obs_time.replace(tzinfo=timezone.utc)

        age_sec = max(0.0, (now - obs_time).total_seconds())
        age_min = age_sec / 60.0

        if age_min <= FRESH_THRESHOLD_MIN:
            freshness = "fresh"
        elif age_min <= DELAYED_THRESHOLD_MIN:
            freshness = "delayed"
        else:
            freshness = "stale"

        return freshness, age_min

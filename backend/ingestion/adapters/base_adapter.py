"""
Base Data Source Adapter Interface.
Phase 9 Operational Data Infrastructure — Multi-Provider Abstraction.
"""
from __future__ import annotations

import time
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone

from core.canonical_observation import (
    CanonicalObservation,
    CanonicalQualityFlag,
    CanonicalProvenance,
    ProcessingStatus,
)
from ingestion.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

logger = logging.getLogger("aerocast.ingestion.adapter")

class DataSourceAdapter(ABC):
    """
    Standard contract for all external data source adapters.
    Encapsulates network retrieval, raw response parsing, physical sanity checks,
    circuit breaking, and conversion into CanonicalObservation objects.
    """

    def __init__(
        self,
        provider_id: str,
        name: str,
        source_type: str,
        priority: int = 1,  # 1 = Primary, 2 = Secondary / Fallback
        expected_interval_minutes: float = 15.0,
        circuit_config: Optional[CircuitBreakerConfig] = None,
    ):
        self.provider_id = provider_id
        self.name = name
        self.source_type = source_type
        self.priority = priority
        self.expected_interval_minutes = expected_interval_minutes
        self.circuit_breaker = CircuitBreaker(provider_id, circuit_config)
        self.last_observation_time: Optional[datetime] = None
        self.last_latency_ms: float = 0.0

    @abstractmethod
    async def fetch_canonical(
        self,
        lat: float,
        lon: float,
        **kwargs: Any,
    ) -> List[CanonicalObservation]:
        """
        Executes raw retrieval, converts into one or more CanonicalObservations,
        and returns them. Must handle internal exceptions cleanly.
        """
        pass

    def is_available(self) -> bool:
        """Returns True if the provider is healthy and circuit is closed/half-open."""
        return self.circuit_breaker.can_execute()

    def get_health_metrics(self) -> Dict[str, Any]:
        """Returns live observability telemetry for monitoring."""
        cb_metrics = self.circuit_breaker.get_metrics()
        now = datetime.now(timezone.utc)

        data_age_sec = None
        if self.last_observation_time is not None:
            data_age_sec = (now - self.last_observation_time).total_seconds()

        return {
            "provider_id": self.provider_id,
            "name": self.name,
            "source_type": self.source_type,
            "priority": "PRIMARY" if self.priority == 1 else "SECONDARY",
            "is_available": self.is_available(),
            "last_latency_ms": round(self.last_latency_ms, 2),
            "data_age_seconds": round(data_age_sec, 1) if data_age_sec is not None else None,
            "expected_interval_min": self.expected_interval_minutes,
            "circuit": cb_metrics,
        }

"""
Operational Provider Manager & Multi-Source Redundancy Engine.
Phase 9 Operational Data Infrastructure.

Orchestrates multi-source ingestion across Radar, Satellite, Lightning, and NWP.
Enforces Primary -> Secondary fallback hierarchy with circuit-breaker protection,
structured logging, fallback event recording, and zero silent fabrication.
"""
from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.canonical_observation import (
    CanonicalObservation,
    CanonicalQualityFlag,
    CanonicalProvenance,
)
from ingestion.adapters.base_adapter import DataSourceAdapter
from ingestion.adapters.radar_adapter import IMDDopplerRadarAdapter, RainViewerRadarAdapter
from ingestion.adapters.satellite_adapter import INSATSatelliteAdapter, OpenMeteoCloudAdapter
from ingestion.adapters.lightning_adapter import BlitzortungLightningAdapter, LightningArchiveAdapter
from ingestion.adapters.nwp_adapter import OpenMeteoNWPAdapter, ClimatologySoundingAdapter

logger = logging.getLogger("aerocast.ingestion.provider_manager")

class ProviderDomainGroup:
    """Encapsulates Primary and Secondary adapters for a single observation domain."""

    def __init__(
        self,
        domain_name: str,
        primary: DataSourceAdapter,
        secondary: DataSourceAdapter,
    ):
        self.domain_name = domain_name
        self.primary = primary
        self.secondary = secondary
        self.active_provider_id: str = primary.provider_id
        self.fallback_active: bool = False
        self.total_fallbacks: int = 0
        self.last_fallback_time: Optional[str] = None
        self.last_fallback_reason: Optional[str] = None


class ProviderManager:
    """
    Central operational manager coordinating external data ingestion with redundancy.
    Guarantees transparent failover, complete provenance tracking, and metric aggregation.
    """

    _instance: Optional[ProviderManager] = None

    def __new__(cls) -> ProviderManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        self._domains: Dict[str, ProviderDomainGroup] = {
            "RADAR": ProviderDomainGroup(
                domain_name="RADAR",
                primary=IMDDopplerRadarAdapter(),
                secondary=RainViewerRadarAdapter(),
            ),
            "SATELLITE": ProviderDomainGroup(
                domain_name="SATELLITE",
                primary=INSATSatelliteAdapter(),
                secondary=OpenMeteoCloudAdapter(),
            ),
            "LIGHTNING": ProviderDomainGroup(
                domain_name="LIGHTNING",
                primary=BlitzortungLightningAdapter(),
                secondary=LightningArchiveAdapter(),
            ),
            "NWP": ProviderDomainGroup(
                domain_name="NWP",
                primary=OpenMeteoNWPAdapter(),
                secondary=ClimatologySoundingAdapter(),
            ),
        }
        self.operational_mode: str = "REAL"  # REAL, REPLAY, TEST, SIMULATION
        self._fallback_history: List[Dict[str, Any]] = []
        self._initialized = True
        logger.info("ProviderManager initialized with 4 observation domains (Radar, Satellite, Lightning, NWP).")

    def set_mode(self, mode: str) -> None:
        """Sets data execution mode: REAL, REPLAY, TEST, SIMULATION."""
        valid_modes = {"REAL", "REPLAY", "TEST", "SIMULATION"}
        if mode not in valid_modes:
            raise ValueError(f"Invalid mode {mode}. Must be one of {valid_modes}")
        self.operational_mode = mode
        logger.info("Operational data mode set to: %s", mode)

    async def fetch_domain(
        self,
        domain_name: str,
        lat: float,
        lon: float,
        **kwargs: Any,
    ) -> Tuple[List[CanonicalObservation], Dict[str, Any]]:
        """
        Fetches observations for a given domain using Primary -> Secondary fallback.
        Returns the list of observations and execution metadata.
        """
        domain_name = domain_name.upper()
        if domain_name not in self._domains:
            raise ValueError(f"Unknown domain {domain_name}. Valid: {list(self._domains.keys())}")

        group = self._domains[domain_name]
        primary = group.primary
        secondary = group.secondary

        # 1. Attempt Primary
        if primary.is_available():
            try:
                obs_list = await primary.fetch_canonical(lat, lon, **kwargs)
                if group.fallback_active:
                    logger.info(
                        "RECOVERY: Domain %s Primary %s has recovered. Restoring primary routing.",
                        domain_name,
                        primary.provider_id,
                    )
                    group.fallback_active = False
                    group.active_provider_id = primary.provider_id

                meta = {
                    "domain": domain_name,
                    "provider_selected": primary.provider_id,
                    "is_fallback": False,
                    "status": "SUCCESS",
                    "observation_count": len(obs_list),
                    "latency_ms": primary.last_latency_ms,
                    "mode": self.operational_mode,
                }
                return obs_list, meta

            except Exception as e:
                logger.warning(
                    "PRIMARY FAILURE in %s: Provider %s failed (%s). Triggering failover to %s.",
                    domain_name,
                    primary.provider_id,
                    e,
                    secondary.provider_id,
                )
                self._record_fallback(group, domain_name, primary.provider_id, secondary.provider_id, str(e))
        else:
            logger.warning(
                "PRIMARY UNAVAILABLE in %s: Provider %s circuit is %s. Routing to secondary %s.",
                domain_name,
                primary.provider_id,
                primary.circuit_breaker.state.name,
                secondary.provider_id,
            )
            self._record_fallback(
                group,
                domain_name,
                primary.provider_id,
                secondary.provider_id,
                f"Circuit breaker {primary.circuit_breaker.state.name}",
            )

        # 2. Attempt Secondary Fallback
        try:
            obs_list = await secondary.fetch_canonical(lat, lon, **kwargs)
            group.fallback_active = True
            group.active_provider_id = secondary.provider_id

            # Ensure provenance notes indicate secondary fallback
            for obs in obs_list:
                if obs.provenance and "SECONDARY FALLBACK" not in " ".join(obs.provenance.transformation_notes):
                    obs.provenance.transformation_notes.append(f"SECONDARY FALLBACK via {secondary.provider_id}")

            meta = {
                "domain": domain_name,
                "provider_selected": secondary.provider_id,
                "provider_failed": primary.provider_id,
                "fallback_reason": group.last_fallback_reason,
                "fallback_timestamp": group.last_fallback_time,
                "is_fallback": True,
                "status": "SUCCESS_FALLBACK",
                "observation_count": len(obs_list),
                "latency_ms": secondary.last_latency_ms,
                "mode": self.operational_mode,
            }
            return obs_list, meta

        except Exception as e:
            logger.error(
                "ALL PROVIDERS FAILED in domain %s: Secondary %s failed (%s). No data available.",
                domain_name,
                secondary.provider_id,
                e,
            )
            meta = {
                "domain": domain_name,
                "provider_selected": None,
                "provider_failed": f"{primary.provider_id}, {secondary.provider_id}",
                "status": "ALL_PROVIDERS_FAILED",
                "error": str(e),
                "observation_count": 0,
                "mode": self.operational_mode,
            }
            return [], meta

    def _record_fallback(
        self,
        group: ProviderDomainGroup,
        domain_name: str,
        primary_id: str,
        secondary_id: str,
        reason: str,
    ) -> None:
        """Records fallback event in memory and logs."""
        now_utc = datetime.now(timezone.utc).isoformat()
        group.total_fallbacks += 1
        group.last_fallback_time = now_utc
        group.last_fallback_reason = reason

        event = {
            "event_id": f"FB-{uuid.uuid4().hex[:8].upper()}",
            "domain": domain_name,
            "primary_provider": primary_id,
            "secondary_provider": secondary_id,
            "fallback_reason": reason,
            "timestamp": now_utc,
        }
        self._fallback_history.append(event)
        if len(self._fallback_history) > 500:
            self._fallback_history.pop(0)

        # Async write to DB if available
        try:
            from db.database import db_manager
            db_manager.execute(
                """
                INSERT INTO fallback_events (event_id, source_type, primary_provider, secondary_provider, fallback_reason, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (event["event_id"], domain_name, primary_id, secondary_id, reason, now_utc),
            )
        except Exception:
            pass  # DB table created during schema update

    def get_system_health(self) -> Dict[str, Any]:
        """Returns comprehensive multi-source health metrics for APIs and Prometheus."""
        health_by_domain = {}
        all_healthy = True

        for name, group in self._domains.items():
            prim_metrics = group.primary.get_health_metrics()
            sec_metrics = group.secondary.get_health_metrics()

            domain_healthy = prim_metrics["is_available"] or sec_metrics["is_available"]
            if not domain_healthy:
                all_healthy = False

            health_by_domain[name] = {
                "active_provider": group.active_provider_id,
                "is_in_fallback": group.fallback_active,
                "total_fallbacks": group.total_fallbacks,
                "last_fallback_time": group.last_fallback_time,
                "last_fallback_reason": group.last_fallback_reason,
                "primary": prim_metrics,
                "secondary": sec_metrics,
            }

        return {
            "status": "HEALTHY" if all_healthy else "DEGRADED",
            "mode": self.operational_mode,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "domains": health_by_domain,
            "recent_fallback_events": self._fallback_history[-10:],
        }

    def get_all_providers(self) -> List[Dict[str, Any]]:
        """Returns flat list of all registered provider adapters."""
        providers = []
        for group in self._domains.values():
            providers.append(group.primary.get_health_metrics())
            providers.append(group.secondary.get_health_metrics())
        return providers

provider_manager = ProviderManager()

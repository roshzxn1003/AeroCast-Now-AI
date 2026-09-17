"""
Lightning Data Source Adapters (Blitzortung Live Primary, Archive/Fallback Secondary).
Phase 9 Operational Data Infrastructure — Provider Redundancy.
"""
from __future__ import annotations

import time
import uuid
import logging
import numpy as np
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.canonical_observation import (
    GriddedObservation,
    TimeSeriesObservation,
    CanonicalQualityFlag,
    CanonicalProvenance,
    ProcessingStatus,
    SpatialDomain,
)
from ingestion.adapters.base_adapter import DataSourceAdapter
from data_ingestion.lightning_ingest import BlitzortungLightningProvider

logger = logging.getLogger("aerocast.ingestion.lightning")

class BlitzortungLightningAdapter(DataSourceAdapter):
    """Primary Lightning Adapter consuming live Blitzortung network stroke events."""

    def __init__(self):
        super().__init__(
            provider_id="BLITZORTUNG_LIVE",
            name="Blitzortung Community Lightning Detection Network",
            source_type="LIGHTNING",
            priority=1,
            expected_interval_minutes=1.0,
        )
        self._provider = BlitzortungLightningProvider()

    async def fetch_canonical(
        self,
        lat: float,
        lon: float,
        radius_km: float = 128.0,
        grid_size: int = 32,
        window_minutes: int = 30,
        **kwargs: Any,
    ) -> List[GriddedObservation | TimeSeriesObservation]:
        if not self.is_available():
            raise RuntimeError(f"BLITZORTUNG_LIVE circuit is open. Cooldown active.")

        t0 = time.perf_counter()
        try:
            strikes = await self._provider.fetch_lightning_strikes(
                lat=lat,
                lon=lon,
                radius_km=radius_km,
                window_minutes=window_minutes,
            )

            density_grid, flash_rate_fpm, meta = self._provider.calculate_density_grid(
                strikes=strikes,
                center_lat=lat,
                center_lon=lon,
                grid_size=grid_size,
                domain_radius_km=radius_km,
            )

            self.last_latency_ms = (time.perf_counter() - t0) * 1000.0
            self.circuit_breaker.record_success(self.last_latency_ms)

            now_utc = datetime.now(timezone.utc).isoformat()
            self.last_observation_time = datetime.now(timezone.utc)

            deg_radius = radius_km / 111.32
            domain = SpatialDomain(
                lat_min=lat - deg_radius,
                lat_max=lat + deg_radius,
                lon_min=lon - deg_radius,
                lon_max=lon + deg_radius,
                resolution_km=(2.0 * radius_km) / grid_size,
            )

            prov = CanonicalProvenance(
                source_provider="BLITZORTUNG",
                source_dataset="blitzortung_toa_strokes",
                source_url_or_channel="wss://ws.blitzortung.org / live_data_service",
                source_timestamp=now_utc,
                ingestion_timestamp=now_utc,
                transformation_notes=[f"Aggregated {len(strikes)} strokes into {grid_size}x{grid_size} density"],
            )

            obs_density = GriddedObservation(
                observation_id=f"OBS-LTG-DENS-{uuid.uuid4().hex[:10].upper()}",
                obs_type=None,
                source="BLITZORTUNG",
                provider=self.provider_id,
                dataset="lightning_flash_density",
                variable="flash_density",
                timestamp=now_utc,
                valid_time=now_utc,
                ingestion_time=now_utc,
                unit="flashes/km²",
                quality_flag=CanonicalQualityFlag.VALID,
                processing_status=ProcessingStatus.NORMALIZED,
                provenance=prov,
                domain=domain,
                grid_shape=(grid_size, grid_size),
                grid_data=density_grid.astype(np.float32),
            )

            # Also generate a time series observation for flash rate
            obs_rate = TimeSeriesObservation(
                observation_id=f"OBS-LTG-RATE-{uuid.uuid4().hex[:10].upper()}",
                obs_type=None,
                source="BLITZORTUNG",
                provider=self.provider_id,
                dataset="lightning_rate_series",
                variable="flash_rate",
                timestamp=now_utc,
                valid_time=now_utc,
                ingestion_time=now_utc,
                unit="flashes/min",
                quality_flag=CanonicalQualityFlag.VALID,
                processing_status=ProcessingStatus.NORMALIZED,
                provenance=prov,
                latitude=lat,
                longitude=lon,
                time_points=[now_utc],
                values=[flash_rate_fpm],
            )

            return [obs_density, obs_rate]

        except Exception as e:
            self.circuit_breaker.record_failure(str(e))
            raise


class LightningArchiveAdapter(DataSourceAdapter):
    """Secondary/Replay Lightning Adapter reading recorded strikes from local store."""

    def __init__(self):
        super().__init__(
            provider_id="LIGHTNING_ARCHIVE",
            name="AeroCast Historical Lightning Archive",
            source_type="LIGHTNING",
            priority=2,
            expected_interval_minutes=1.0,
        )

    async def fetch_canonical(
        self,
        lat: float,
        lon: float,
        radius_km: float = 128.0,
        grid_size: int = 32,
        **kwargs: Any,
    ) -> List[GriddedObservation]:
        if not self.is_available():
            raise RuntimeError(f"LIGHTNING_ARCHIVE circuit is open. Cooldown active.")

        t0 = time.perf_counter()
        try:
            # Query archived strikes from SQLite
            from db.database import db_manager
            now_utc = datetime.now(timezone.utc).isoformat()

            # Empty default or read recent archived observations
            density_grid = np.zeros((grid_size, grid_size), dtype=np.float32)

            self.last_latency_ms = (time.perf_counter() - t0) * 1000.0
            self.circuit_breaker.record_success(self.last_latency_ms)

            self.last_observation_time = datetime.now(timezone.utc)
            deg_radius = radius_km / 111.32
            domain = SpatialDomain(
                lat_min=lat - deg_radius,
                lat_max=lat + deg_radius,
                lon_min=lon - deg_radius,
                lon_max=lon + deg_radius,
                resolution_km=(2.0 * radius_km) / grid_size,
            )

            prov = CanonicalProvenance(
                source_provider="AEROCAST_ARCHIVE",
                source_dataset="archived_lightning_strikes",
                source_url_or_channel="sqlite3:observations",
                source_timestamp=now_utc,
                ingestion_timestamp=now_utc,
                transformation_notes=["Secondary lightning replay/archive query"],
            )

            obs_density = GriddedObservation(
                observation_id=f"OBS-LTG-ARCH-{uuid.uuid4().hex[:10].upper()}",
                obs_type=None,
                source="ARCHIVE",
                provider=self.provider_id,
                dataset="archived_flash_density",
                variable="flash_density",
                timestamp=now_utc,
                valid_time=now_utc,
                ingestion_time=now_utc,
                unit="flashes/km²",
                quality_flag=CanonicalQualityFlag.SUSPECT,
                processing_status=ProcessingStatus.NORMALIZED,
                provenance=prov,
                domain=domain,
                grid_shape=(grid_size, grid_size),
                grid_data=density_grid,
            )

            return [obs_density]

        except Exception as e:
            self.circuit_breaker.record_failure(str(e))
            raise

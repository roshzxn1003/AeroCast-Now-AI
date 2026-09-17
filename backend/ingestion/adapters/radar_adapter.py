"""
Radar Data Source Adapters (IMD Primary, RainViewer Secondary).
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
    CanonicalQualityFlag,
    CanonicalProvenance,
    ProcessingStatus,
    SpatialDomain,
)
from ingestion.adapters.base_adapter import DataSourceAdapter
from data_ingestion.radar_ingest import CompositeRadarProvider

logger = logging.getLogger("aerocast.ingestion.radar")

class IMDDopplerRadarAdapter(DataSourceAdapter):
    """Primary Radar Adapter querying official IMD Doppler Weather Radar feeds."""

    def __init__(self):
        super().__init__(
            provider_id="IMD_DWR",
            name="IMD Doppler Weather Radar Network",
            source_type="RADAR",
            priority=1,
            expected_interval_minutes=10.0,
        )
        self._provider = CompositeRadarProvider()

    async def fetch_canonical(
        self,
        lat: float,
        lon: float,
        station_name: str = "Chennai DWR (Sriharikota/Port)",
        grid_size: int = 32,
        range_km: float = 250.0,
        **kwargs: Any,
    ) -> List[GriddedObservation]:
        if not self.is_available():
            raise RuntimeError(f"IMD_DWR circuit is open. Cooldown active.")

        t0 = time.perf_counter()
        try:
            # Force primary IMD
            dbz_grid, vil_grid, meta = await self._provider.fetch_radar_grid(
                station_id=station_name,
                lat=lat,
                lon=lon,
                grid_size=grid_size,
                range_km=range_km,
            )
            raw_source = meta.get("source", "UNKNOWN")

            # Check if IMD returned real data or failed
            if "IMD" not in raw_source:
                raise ValueError(f"IMD feed returned {raw_source} rather than authentic DWR composite")

            self.last_latency_ms = (time.perf_counter() - t0) * 1000.0
            self.circuit_breaker.record_success(self.last_latency_ms)

            now_utc = datetime.now(timezone.utc).isoformat()
            self.last_observation_time = datetime.now(timezone.utc)

            domain = SpatialDomain(
                lat_min=lat - 1.25,
                lat_max=lat + 1.25,
                lon_min=lon - 1.25,
                lon_max=lon + 1.25,
                resolution_km=range_km / grid_size,
            )

            prov = CanonicalProvenance(
                source_provider="IMD",
                source_dataset="imd_dwr_composite",
                source_url_or_channel="https://mausam.imd.gov.in/Radar/",
                source_timestamp=meta.get("timestamp", now_utc),
                ingestion_timestamp=now_utc,
            )

            obs_dbz = GriddedObservation(
                observation_id=f"OBS-RADAR-DBZ-{uuid.uuid4().hex[:10].upper()}",
                obs_type=None,
                source="IMD",
                provider=self.provider_id,
                dataset="dwr_reflectivity",
                variable="reflectivity",
                timestamp=meta.get("timestamp", now_utc),
                valid_time=meta.get("timestamp", now_utc),
                ingestion_time=now_utc,
                unit="dBZ",
                quality_flag=CanonicalQualityFlag.VALID,
                processing_status=ProcessingStatus.NORMALIZED,
                provenance=prov,
                domain=domain,
                grid_shape=(grid_size, grid_size),
                grid_data=dbz_grid.astype(np.float32),
            )

            obs_vil = GriddedObservation(
                observation_id=f"OBS-RADAR-VIL-{uuid.uuid4().hex[:10].upper()}",
                obs_type=None,
                source="IMD",
                provider=self.provider_id,
                dataset="dwr_vil",
                variable="vertically_integrated_liquid",
                timestamp=meta.get("timestamp", now_utc),
                valid_time=meta.get("timestamp", now_utc),
                ingestion_time=now_utc,
                unit="kg/m²",
                quality_flag=CanonicalQualityFlag.VALID,
                processing_status=ProcessingStatus.NORMALIZED,
                provenance=prov,
                domain=domain,
                grid_shape=(grid_size, grid_size),
                grid_data=vil_grid.astype(np.float32),
            )

            return [obs_dbz, obs_vil]

        except Exception as e:
            self.circuit_breaker.record_failure(str(e))
            raise


class RainViewerRadarAdapter(DataSourceAdapter):
    """Secondary Radar Adapter querying RainViewer Global Radar Mosaic API."""

    def __init__(self):
        super().__init__(
            provider_id="RAINVIEWER_RADAR",
            name="RainViewer Global Radar Mosaic",
            source_type="RADAR",
            priority=2,
            expected_interval_minutes=10.0,
        )
        self._provider = CompositeRadarProvider()

    async def fetch_canonical(
        self,
        lat: float,
        lon: float,
        station_name: str = "Chennai DWR (Sriharikota/Port)",
        grid_size: int = 32,
        range_km: float = 250.0,
        **kwargs: Any,
    ) -> List[GriddedObservation]:
        if not self.is_available():
            raise RuntimeError(f"RAINVIEWER_RADAR circuit is open. Cooldown active.")

        t0 = time.perf_counter()
        try:
            # Explicit RainViewer fetch
            dbz_grid, vil_grid, meta = await self._provider.rainviewer.fetch_radar_grid(
                station_id=station_name,
                lat=lat,
                lon=lon,
                grid_size=grid_size,
                range_km=range_km,
            )

            self.last_latency_ms = (time.perf_counter() - t0) * 1000.0
            self.circuit_breaker.record_success(self.last_latency_ms)

            now_utc = datetime.now(timezone.utc).isoformat()
            self.last_observation_time = datetime.now(timezone.utc)

            domain = SpatialDomain(
                lat_min=lat - 1.25,
                lat_max=lat + 1.25,
                lon_min=lon - 1.25,
                lon_max=lon + 1.25,
                resolution_km=range_km / grid_size,
            )

            prov = CanonicalProvenance(
                source_provider="RAINVIEWER",
                source_dataset="rainviewer_mosaic_tile",
                source_url_or_channel="https://api.rainviewer.com/public/weather-maps.json",
                source_timestamp=meta.get("timestamp", now_utc),
                ingestion_timestamp=now_utc,
                transformation_notes=["Secondary fallback radar mosaic"],
            )

            obs_dbz = GriddedObservation(
                observation_id=f"OBS-RADAR-RV-DBZ-{uuid.uuid4().hex[:10].upper()}",
                obs_type=None,
                source="RAINVIEWER",
                provider=self.provider_id,
                dataset="radar_mosaic_reflectivity",
                variable="reflectivity",
                timestamp=meta.get("timestamp", now_utc),
                valid_time=meta.get("timestamp", now_utc),
                ingestion_time=now_utc,
                unit="dBZ",
                quality_flag=CanonicalQualityFlag.VALID,
                processing_status=ProcessingStatus.NORMALIZED,
                provenance=prov,
                domain=domain,
                grid_shape=(grid_size, grid_size),
                grid_data=dbz_grid.astype(np.float32),
            )

            obs_vil = GriddedObservation(
                observation_id=f"OBS-RADAR-RV-VIL-{uuid.uuid4().hex[:10].upper()}",
                obs_type=None,
                source="RAINVIEWER",
                provider=self.provider_id,
                dataset="radar_mosaic_vil",
                variable="vertically_integrated_liquid",
                timestamp=meta.get("timestamp", now_utc),
                valid_time=meta.get("timestamp", now_utc),
                ingestion_time=now_utc,
                unit="kg/m²",
                quality_flag=CanonicalQualityFlag.VALID,
                processing_status=ProcessingStatus.NORMALIZED,
                provenance=prov,
                domain=domain,
                grid_shape=(grid_size, grid_size),
                grid_data=vil_grid.astype(np.float32),
            )

            return [obs_dbz, obs_vil]

        except Exception as e:
            self.circuit_breaker.record_failure(str(e))
            raise

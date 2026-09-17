"""
Satellite Data Source Adapters (INSAT Primary, Open-Meteo Cloud Secondary).
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
from data_ingestion.satellite_ingest import INSATSatelliteProvider

logger = logging.getLogger("aerocast.ingestion.satellite")

class INSATSatelliteAdapter(DataSourceAdapter):
    """Primary Satellite Adapter querying ISRO / IMD INSAT-3D/3DR geostationary imagery."""

    def __init__(self):
        super().__init__(
            provider_id="INSAT_3D",
            name="ISRO/IMD INSAT-3D/3DR Geostationary Satellite",
            source_type="SATELLITE",
            priority=1,
            expected_interval_minutes=15.0,
        )
        self._provider = INSATSatelliteProvider()

    async def fetch_canonical(
        self,
        lat: float,
        lon: float,
        grid_size: int = 32,
        domain_deg: float = 2.5,
        **kwargs: Any,
    ) -> List[GriddedObservation]:
        if not self.is_available():
            raise RuntimeError(f"INSAT_3D circuit is open. Cooldown active.")

        t0 = time.perf_counter()
        try:
            grid, meta = await self._provider.fetch_satellite_grid(
                lat=lat,
                lon=lon,
                grid_size=grid_size,
                domain_deg=domain_deg,
            )

            if meta.get("status") == "unavailable":
                raise ValueError("INSAT-3D satellite feed returned unavailable status")

            self.last_latency_ms = (time.perf_counter() - t0) * 1000.0
            self.circuit_breaker.record_success(self.last_latency_ms)

            now_utc = datetime.now(timezone.utc).isoformat()
            self.last_observation_time = datetime.now(timezone.utc)

            domain = SpatialDomain(
                lat_min=lat - domain_deg / 2.0,
                lat_max=lat + domain_deg / 2.0,
                lon_min=lon - domain_deg / 2.0,
                lon_max=lon + domain_deg / 2.0,
                resolution_km=(domain_deg * 111.32) / grid_size,
            )

            prov = CanonicalProvenance(
                source_provider="ISRO_IMD",
                source_dataset="insat_3d_tir1",
                source_url_or_channel="https://internal.imd.gov.in/section/sat/3Dasiasec_ir1.jpg",
                source_timestamp=meta.get("timestamp", now_utc),
                ingestion_timestamp=now_utc,
                transformation_notes=["Thermal IR 10.8um calibrated brightness temperature"],
            )

            obs_tir = GriddedObservation(
                observation_id=f"OBS-SAT-TIR-{uuid.uuid4().hex[:10].upper()}",
                obs_type=None,
                source="ISRO_IMD",
                provider=self.provider_id,
                dataset="insat_3d_tir1",
                variable="brightness_temperature",
                timestamp=meta.get("timestamp", now_utc),
                valid_time=meta.get("timestamp", now_utc),
                ingestion_time=now_utc,
                unit="°C",
                quality_flag=CanonicalQualityFlag.VALID,
                processing_status=ProcessingStatus.NORMALIZED,
                provenance=prov,
                domain=domain,
                grid_shape=(grid_size, grid_size),
                grid_data=grid.astype(np.float32),
            )

            return [obs_tir]

        except Exception as e:
            self.circuit_breaker.record_failure(str(e))
            raise


class OpenMeteoCloudAdapter(DataSourceAdapter):
    """Secondary Satellite/Cloud Adapter querying Open-Meteo Convective Cloud Cover."""

    def __init__(self):
        super().__init__(
            provider_id="OPEN_METEO_CLOUD",
            name="Open-Meteo Convective Cloud & IR Proxy",
            source_type="SATELLITE",
            priority=2,
            expected_interval_minutes=15.0,
        )

    async def fetch_canonical(
        self,
        lat: float,
        lon: float,
        grid_size: int = 32,
        domain_deg: float = 2.5,
        **kwargs: Any,
    ) -> List[GriddedObservation]:
        if not self.is_available():
            raise RuntimeError(f"OPEN_METEO_CLOUD circuit is open. Cooldown active.")

        t0 = time.perf_counter()
        try:
            from data_ingestion.weather_ingest import OpenMeteoWeatherProvider
            provider = OpenMeteoWeatherProvider()
            obs = await provider.fetch_station_observation("CLOUD_PROXY", lat, lon)

            if not obs.quality.valid:
                raise ValueError("Open-Meteo cloud query returned invalid status")

            cloud_cover = obs.cloud_cover_pct if obs.cloud_cover_pct is not None else 50.0
            # Convert cloud cover to proxy TIR: 0% -> +25°C, 100% -> -65°C
            proxy_tir_c = 25.0 - (cloud_cover / 100.0) * 90.0
            grid = np.full((grid_size, grid_size), proxy_tir_c, dtype=np.float32)

            self.last_latency_ms = (time.perf_counter() - t0) * 1000.0
            self.circuit_breaker.record_success(self.last_latency_ms)

            now_utc = datetime.now(timezone.utc).isoformat()
            self.last_observation_time = datetime.now(timezone.utc)

            domain = SpatialDomain(
                lat_min=lat - domain_deg / 2.0,
                lat_max=lat + domain_deg / 2.0,
                lon_min=lon - domain_deg / 2.0,
                lon_max=lon + domain_deg / 2.0,
                resolution_km=(domain_deg * 111.32) / grid_size,
            )

            prov = CanonicalProvenance(
                source_provider="OPEN_METEO",
                source_dataset="open_meteo_cloud_ir_proxy",
                source_url_or_channel="https://api.open-meteo.com/v1/forecast",
                source_timestamp=now_utc,
                ingestion_timestamp=now_utc,
                transformation_notes=["Secondary cloud proxy brightness temperature conversion"],
            )

            obs_tir = GriddedObservation(
                observation_id=f"OBS-SAT-OM-TIR-{uuid.uuid4().hex[:10].upper()}",
                obs_type=None,
                source="OPEN_METEO",
                provider=self.provider_id,
                dataset="open_meteo_cloud_proxy",
                variable="brightness_temperature",
                timestamp=now_utc,
                valid_time=now_utc,
                ingestion_time=now_utc,
                unit="°C",
                quality_flag=CanonicalQualityFlag.SUSPECT,  # Proxy flag
                processing_status=ProcessingStatus.NORMALIZED,
                provenance=prov,
                domain=domain,
                grid_shape=(grid_size, grid_size),
                grid_data=grid,
            )

            return [obs_tir]

        except Exception as e:
            self.circuit_breaker.record_failure(str(e))
            raise

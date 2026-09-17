"""
NWP & Atmospheric Sounding Adapters (Open-Meteo Primary, Climatology Secondary).
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
    ScalarObservation,
    GriddedObservation,
    CanonicalQualityFlag,
    CanonicalProvenance,
    ProcessingStatus,
    SpatialDomain,
)
from ingestion.adapters.base_adapter import DataSourceAdapter
from data_ingestion.weather_ingest import OpenMeteoWeatherProvider

logger = logging.getLogger("aerocast.ingestion.nwp")

class OpenMeteoNWPAdapter(DataSourceAdapter):
    """Primary NWP & Sounding Adapter querying Open-Meteo High-Resolution Convective Analysis."""

    def __init__(self):
        super().__init__(
            provider_id="OPEN_METEO_NWP",
            name="Open-Meteo High-Resolution Convective Model",
            source_type="NWP",
            priority=1,
            expected_interval_minutes=60.0,
        )
        self._provider = OpenMeteoWeatherProvider()

    async def fetch_canonical(
        self,
        lat: float,
        lon: float,
        station_id: str = "NWP_POINT",
        station_name: str = "",
        **kwargs: Any,
    ) -> List[ScalarObservation]:
        if not self.is_available():
            raise RuntimeError(f"OPEN_METEO_NWP circuit is open. Cooldown active.")

        t0 = time.perf_counter()
        try:
            obs = await self._provider.fetch_station_observation(
                station_id=station_id,
                lat=lat,
                lon=lon,
                station_name=station_name,
            )

            if not obs.quality.valid:
                raise ValueError(f"Open-Meteo NWP query failed: {obs.quality.issues}")

            self.last_latency_ms = (time.perf_counter() - t0) * 1000.0
            self.circuit_breaker.record_success(self.last_latency_ms)

            now_utc = datetime.now(timezone.utc).isoformat()
            self.last_observation_time = datetime.now(timezone.utc)

            prov = CanonicalProvenance(
                source_provider="OPEN_METEO",
                source_dataset="open_meteo_convective_nwp",
                source_url_or_channel="https://api.open-meteo.com/v1/forecast",
                source_timestamp=obs.timestamp or now_utc,
                ingestion_timestamp=now_utc,
                transformation_notes=["Direct NWP parameter extraction"],
            )

            canonical_list: List[ScalarObservation] = []

            # Variables to extract
            var_specs = [
                ("cape", obs.cape_j_kg, "J/kg", 0.0, 6000.0),
                ("cin", obs.cin_j_kg, "J/kg", 0.0, 1000.0),
                ("lifted_index", obs.lifted_index_c, "°C", -15.0, 15.0),
                ("precipitable_water", obs.precipitable_water_mm, "mm", 0.0, 100.0),
                ("wind_shear_0_6km", obs.wind_shear_0_6km_kts, "kts", 0.0, 120.0),
                ("temperature", obs.temperature_c, "°C", -10.0, 55.0),
                ("relative_humidity", obs.relative_humidity_pct, "%", 0.0, 100.0),
                ("surface_pressure", obs.pressure_hpa, "hPa", 800.0, 1060.0),
            ]

            for var_name, val, unit, v_min, v_max in var_specs:
                if val is not None:
                    q_flag = CanonicalQualityFlag.VALID
                    if not (v_min <= val <= v_max):
                        q_flag = CanonicalQualityFlag.SUSPECT

                    canonical_list.append(
                        ScalarObservation(
                            observation_id=f"OBS-NWP-{var_name.upper()[:4]}-{uuid.uuid4().hex[:8].upper()}",
                            obs_type=None,
                            source="OPEN_METEO",
                            provider=self.provider_id,
                            dataset="open_meteo_convective_nwp",
                            variable=var_name,
                            timestamp=obs.timestamp or now_utc,
                            valid_time=obs.timestamp or now_utc,
                            ingestion_time=now_utc,
                            unit=unit,
                            quality_flag=q_flag,
                            processing_status=ProcessingStatus.NORMALIZED,
                            provenance=prov,
                            latitude=lat,
                            longitude=lon,
                            value=float(val),
                            metadata={"uncertainty": None},
                        )
                    )

            return canonical_list

        except Exception as e:
            self.circuit_breaker.record_failure(str(e))
            raise


class ClimatologySoundingAdapter(DataSourceAdapter):
    """
    Secondary Sounding Adapter returning regional tropical climatology.
    Explicitly tags all observations as ESTIMATED/IMPUTED to maintain scientific integrity.
    """

    def __init__(self):
        super().__init__(
            provider_id="CLIMATOLOGY_SOUNDING",
            name="Regional Tropical Climatological Atmospheric Sounding",
            source_type="NWP",
            priority=2,
            expected_interval_minutes=60.0,
        )

    async def fetch_canonical(
        self,
        lat: float,
        lon: float,
        station_id: str = "CLIMATOLOGY",
        **kwargs: Any,
    ) -> List[ScalarObservation]:
        if not self.is_available():
            raise RuntimeError(f"CLIMATOLOGY_SOUNDING circuit is open.")

        t0 = time.perf_counter()
        now_utc = datetime.now(timezone.utc).isoformat()
        self.last_latency_ms = (time.perf_counter() - t0) * 1000.0
        self.circuit_breaker.record_success(self.last_latency_ms)
        self.last_observation_time = datetime.now(timezone.utc)

        prov = CanonicalProvenance(
            source_provider="CLIMATOLOGY_BASELINE",
            source_dataset="regional_tropical_profile",
            source_url_or_channel="in_memory_climatology",
            source_timestamp=now_utc,
            ingestion_timestamp=now_utc,
            transformation_notes=["SECONDARY FALLBACK: Imputed regional convective climatology (ESTIMATED)"],
        )

        # Baseline climatological values for tropical coastal boundary
        climatology_values = [
            ("cape", 1200.0, "J/kg"),
            ("cin", 45.0, "J/kg"),
            ("lifted_index", -2.5, "°C"),
            ("precipitable_water", 42.0, "mm"),
            ("wind_shear_0_6km", 18.0, "kts"),
            ("temperature", 28.5, "°C"),
            ("relative_humidity", 78.0, "%"),
            ("surface_pressure", 1010.0, "hPa"),
        ]

        canonical_list: List[ScalarObservation] = []
        for var_name, val, unit in climatology_values:
            canonical_list.append(
                ScalarObservation(
                    observation_id=f"OBS-CLIM-{var_name.upper()[:4]}-{uuid.uuid4().hex[:8].upper()}",
                    obs_type=None,
                    source="CLIMATOLOGY",
                    provider=self.provider_id,
                    dataset="regional_tropical_profile",
                    variable=var_name,
                    timestamp=now_utc,
                    valid_time=now_utc,
                    ingestion_time=now_utc,
                    unit=unit,
                    quality_flag=CanonicalQualityFlag.ESTIMATED,  # Explicitly flagged
                    processing_status=ProcessingStatus.NORMALIZED,
                    provenance=prov,
                    latitude=lat,
                    longitude=lon,
                    value=float(val),
                    metadata={"uncertainty": 200.0 if var_name == "cape" else 5.0},
                )
            )

        return canonical_list

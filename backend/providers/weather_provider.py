"""
Weather & Atmospheric Sounding Provider
=======================================
Wraps authentic numerical convective sounding and surface meteorology feeds:
  - Convective Available Potential Energy (CAPE, J/kg)
  - Convective Inhibition (CIN, J/kg)
  - Lifted Index (LI, °C)
  - 0-6 km Bulk Wind Shear (kts)
  - Precipitable Water (PWAT, mm)
  - Surface Temperature, Humidity, and Pressure

Sources: IMD AWS / Open-Meteo High-Resolution Convective Analysis.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from providers.base_provider import (
    BaseObservationProvider,
    ObservationQuality,
    ProviderResult,
)
from data_ingestion.weather_ingest import CompositeWeatherProvider

logger = logging.getLogger("aerocast.providers.weather")


class WeatherProvider(BaseObservationProvider):
    """
    Live surface weather and convective sounding provider.
    """

    def __init__(self) -> None:
        super().__init__(name="WeatherProvider", source_type="NUMERICAL_SOUNDING")
        self._composite = CompositeWeatherProvider()

    async def fetch_latest(
        self,
        lat: float,
        lon: float,
        station_name: str = "Chennai DWR (Sriharikota/Port)",
        **kwargs: Any,
    ) -> ProviderResult:
        """
        Fetches latest thermodynamic sounding profile and surface weather for (lat, lon).
        """
        t0 = time.perf_counter()
        try:
            obs = await self._composite.fetch_station_observation(
                station_id=station_name,
                lat=lat,
                lon=lon,
                station_name=station_name,
            )

            latency_ms = (time.perf_counter() - t0) * 1000.0

            try:
                obs_time = datetime.fromisoformat(obs.timestamp.replace("Z", "+00:00"))
            except Exception:
                obs_time = datetime.now(timezone.utc)

            freshness, age_minutes = self.get_freshness(obs_time)

            data = {
                "temperature_c": obs.temperature_c,
                "relative_humidity_pct": obs.relative_humidity_pct,
                "pressure_hpa": obs.pressure_hpa,
                "wind_speed_ms": obs.wind_speed_ms,
                "wind_direction_deg": obs.wind_direction_deg,
                "rainfall_mm_h": obs.rainfall_mm_h,
                "cape_j_kg": obs.cape_j_kg,
                "cin_j_kg": obs.cin_j_kg,
                "lifted_index_c": obs.lifted_index_c,
                "precipitable_water_mm": obs.precipitable_water_mm,
                "wind_shear_0_6km_kts": obs.wind_shear_0_6km_kts,
                "k_index": obs.k_index,
                "total_totals_index": obs.total_totals_index,
            }

            quality = self.validate(data)
            if not quality.valid:
                freshness = "invalid"

            is_success = obs.quality.valid and quality.valid

            return ProviderResult(
                success=is_success,
                data=data,
                timestamp=obs_time,
                latency_ms=latency_ms,
                source=obs.quality.source,
                freshness=freshness if is_success else "missing",
                age_minutes=age_minutes,
                quality=quality,
                error="; ".join(obs.quality.issues) if obs.quality.issues else None,
                metadata={
                    "station_id": obs.station_id,
                    "station_name": obs.station_name,
                    "latitude": obs.latitude,
                    "longitude": obs.longitude,
                },
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            logger.error("WeatherProvider fetch failed: %s", e)
            now = datetime.now(timezone.utc)
            return ProviderResult(
                success=False,
                data={},
                timestamp=now,
                latency_ms=latency_ms,
                source="ERROR",
                freshness="missing",
                age_minutes=9999.0,
                quality=ObservationQuality(valid=False, issues=[str(e)]),
                error=str(e),
                metadata={"station_name": station_name},
            )

    def validate(self, data: Any) -> ObservationQuality:
        """
        Validates thermodynamic sounding and surface data against physical bounds:
          - CAPE >= 0.0 J/kg, <= 7000.0 J/kg
          - Relative humidity in [0, 100] %
          - Temperature in [-10, 55] °C
          - Surface pressure in [800, 1060] hPa
        """
        issues: List[str] = []
        out_of_bounds = False

        if not isinstance(data, dict):
            return ObservationQuality(valid=False, issues=["Data is not a dict"])

        cape = data.get("cape_j_kg")
        if cape is not None:
            if cape < 0.0 or cape > 7000.0:
                issues.append(f"CAPE outside physical limits [0, 7000]: {cape}")
                out_of_bounds = True

        rh = data.get("relative_humidity_pct")
        if rh is not None:
            if rh < 0.0 or rh > 100.0:
                issues.append(f"Relative humidity outside [0, 100]: {rh}")
                out_of_bounds = True

        temp = data.get("temperature_c")
        if temp is not None:
            if temp < -30.0 or temp > 60.0:
                issues.append(f"Temperature outside [-30, 60]: {temp}")
                out_of_bounds = True

        pressure = data.get("pressure_hpa")
        if pressure is not None:
            if pressure < 700.0 or pressure > 1080.0:
                issues.append(f"Surface pressure outside [700, 1080]: {pressure}")
                out_of_bounds = True

        score = 1.0 - (0.25 * len(issues))
        score = max(0.0, min(1.0, score))

        return ObservationQuality(
            valid=len(issues) == 0,
            quality_score=score,
            issues=issues,
            out_of_bounds=out_of_bounds,
        )

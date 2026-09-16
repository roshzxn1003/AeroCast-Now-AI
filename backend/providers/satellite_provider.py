"""
Satellite Observation Provider
==============================
Wraps ISRO / IMD INSAT-3D/3DR geostationary meteorological satellite acquisition.
Extracts Thermal Infrared 1 (TIR1: 10.8 µm) brightness temperatures (°C).

Outputs calibrated physical grid:
  - Channel 2: Satellite Brightness Temperature (TIR: [-85.0, +35.0] °C)
    (Cold cloud tops e.g. < -40°C indicate deep convective thunderstorm updrafts).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from providers.base_provider import (
    BaseObservationProvider,
    ObservationQuality,
    ProviderResult,
)
from data_ingestion.satellite_ingest import INSATSatelliteProvider

logger = logging.getLogger("aerocast.providers.satellite")


class SatelliteProvider(BaseObservationProvider):
    """
    Live INSAT-3D/3DR satellite provider producing physical (32, 32) Thermal IR brightness temperature grids.
    """

    def __init__(self) -> None:
        super().__init__(name="SatelliteProvider", source_type="GEO_SATELLITE")
        self._insat = INSATSatelliteProvider()

    async def fetch_latest(
        self,
        lat: float,
        lon: float,
        grid_size: int = 32,
        domain_deg: float = 2.5,
        **kwargs: Any,
    ) -> ProviderResult:
        """
        Fetches latest INSAT-3D image, crops domain around (lat, lon), and decodes to (32, 32) TIR grid.
        """
        t0 = time.perf_counter()
        try:
            tir_grid, meta = await self._insat.fetch_satellite_grid(
                lat=lat,
                lon=lon,
                grid_size=grid_size,
                domain_deg=domain_deg,
            )

            latency_ms = (time.perf_counter() - t0) * 1000.0
            source = meta.get("source", "UNKNOWN")
            timestamp_str = meta.get("timestamp")

            if timestamp_str:
                try:
                    obs_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                except Exception:
                    obs_time = datetime.now(timezone.utc)
            else:
                obs_time = datetime.now(timezone.utc)

            freshness, age_minutes = self.get_freshness(obs_time)

            min_tir = float(np.min(tir_grid))
            mean_tir = float(np.mean(tir_grid))
            cold_core_count = int(np.sum(tir_grid < -40.0))

            data = {
                "tir_grid": tir_grid,
                "min_tir_c": min_tir,
                "mean_tir_c": mean_tir,
                "cold_cloud_pixels": cold_core_count,
            }

            quality = self.validate(data)
            if not quality.valid:
                freshness = "invalid"

            is_success = (source in ("LIVE-INSAT-3D", "CACHE-INSAT-3D")) and quality.valid

            return ProviderResult(
                success=is_success,
                data=data,
                timestamp=obs_time,
                latency_ms=latency_ms,
                source=source,
                freshness=freshness if is_success else ("missing" if "BASELINE" in source else "invalid"),
                age_minutes=age_minutes,
                quality=quality,
                error=meta.get("error"),
                metadata={
                    "channel": "TIR1 (10.8 µm)",
                    "grid_size": grid_size,
                    "domain_deg": domain_deg,
                    **meta,
                },
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            logger.error("SatelliteProvider fetch failed: %s", e)
            default_grid = np.full((grid_size, grid_size), 22.0, dtype=np.float32)
            now = datetime.now(timezone.utc)
            return ProviderResult(
                success=False,
                data={"tir_grid": default_grid, "min_tir_c": 22.0, "mean_tir_c": 22.0, "cold_cloud_pixels": 0},
                timestamp=now,
                latency_ms=latency_ms,
                source="ERROR",
                freshness="missing",
                age_minutes=9999.0,
                quality=ObservationQuality(valid=False, issues=[str(e)]),
                error=str(e),
                metadata={"grid_size": grid_size},
            )

    def validate(self, data: Any) -> ObservationQuality:
        """
        Validates satellite TIR array:
          - Shape must be (32, 32)
          - No NaNs or Infs
          - TIR brightness temperatures within physical limits [-85.0°C, +35.0°C]
        """
        issues: List[str] = []
        missing: List[str] = []

        if not isinstance(data, dict):
            return ObservationQuality(valid=False, issues=["Data is not a dict"])

        if "tir_grid" not in data:
            return ObservationQuality(valid=False, missing_fields=["tir_grid"], issues=["Missing tir_grid field"])

        tir = data["tir_grid"]

        if not isinstance(tir, np.ndarray):
            return ObservationQuality(valid=False, issues=["tir_grid is not numpy ndarray"])

        if tir.shape != (32, 32):
            issues.append(f"Invalid grid shape: tir={tir.shape}, expected (32, 32)")

        if np.any(np.isnan(tir)):
            issues.append("tir_grid contains NaN values")

        if np.any(np.isinf(tir)):
            issues.append("tir_grid contains Inf values")

        out_of_bounds = False
        if np.any(tir < -85.0) or np.any(tir > 35.0):
            issues.append(f"tir values outside [-85, +35] °C: min={np.min(tir)}, max={np.max(tir)}")
            out_of_bounds = True

        score = 1.0 - (0.3 * len(issues))
        score = max(0.0, min(1.0, score))

        return ObservationQuality(
            valid=len(issues) == 0,
            quality_score=score,
            issues=issues,
            out_of_bounds=out_of_bounds,
        )

"""
Radar Observation Provider
==========================
Wraps Doppler Weather Radar acquisition for real-time nowcasting.
Attempts live IMD Doppler Radar products first, then RainViewer global radar tile mosaic.

Outputs calibrated physical grids:
  - Channel 0: Radar Reflectivity (dBZ: [0.0, 75.0])
  - Channel 1: Vertically Integrated Liquid (VIL: [0.0, 65.0] kg/m²)
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
from data_ingestion.radar_ingest import CompositeRadarProvider

logger = logging.getLogger("aerocast.providers.radar")


class RadarProvider(BaseObservationProvider):
    """
    Live Doppler Weather Radar provider producing physical (32, 32) dBZ and VIL grids.
    """

    def __init__(self) -> None:
        super().__init__(name="RadarProvider", source_type="DWR_RADAR")
        self._composite = CompositeRadarProvider()

    async def fetch_latest(
        self,
        lat: float,
        lon: float,
        station_name: str = "Chennai DWR (Sriharikota/Port)",
        grid_size: int = 32,
        range_km: float = 250.0,
        **kwargs: Any,
    ) -> ProviderResult:
        """
        Fetches the latest radar volume/mosaic scan and decodes to (32, 32) dBZ and VIL grids.
        """
        t0 = time.perf_counter()
        try:
            dbz_grid, vil_grid, meta = await self._composite.fetch_radar_grid(
                station_id=station_name,
                lat=lat,
                lon=lon,
                grid_size=grid_size,
                range_km=range_km,
            )

            latency_ms = (time.perf_counter() - t0) * 1000.0
            raw_source = meta.get("source", "UNKNOWN")
            timestamp_str = meta.get("timestamp")

            if timestamp_str:
                try:
                    obs_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                except Exception:
                    obs_time = datetime.now(timezone.utc)
            else:
                obs_time = datetime.now(timezone.utc)

            freshness, age_minutes = self.get_freshness(obs_time)

            data = {
                "dbz_grid": dbz_grid,
                "vil_grid": vil_grid,
                "max_dbz": float(np.max(dbz_grid)),
                "max_vil": float(np.max(vil_grid)),
                "mean_dbz": float(np.mean(dbz_grid)),
            }

            quality = self.validate(data)
            if not quality.valid:
                freshness = "invalid"

            is_success = (raw_source in ("LIVE-IMD-DWR", "LIVE-RAINVIEWER", "CACHE-IMD-DWR")) and quality.valid

            return ProviderResult(
                success=is_success,
                data=data,
                timestamp=obs_time,
                latency_ms=latency_ms,
                source=raw_source,
                freshness=freshness if is_success else ("missing" if "UNAVAILABLE" in raw_source else "invalid"),
                age_minutes=age_minutes,
                quality=quality,
                error=meta.get("error"),
                metadata={
                    "station_name": station_name,
                    "grid_size": grid_size,
                    "range_km": range_km,
                    **meta,
                },
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            logger.error("RadarProvider fetch failed: %s", e)
            empty = np.zeros((grid_size, grid_size), dtype=np.float32)
            now = datetime.now(timezone.utc)
            return ProviderResult(
                success=False,
                data={"dbz_grid": empty, "vil_grid": empty, "max_dbz": 0.0, "max_vil": 0.0, "mean_dbz": 0.0},
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
        Validates radar arrays:
          - Shape must be (32, 32)
          - No NaNs or Infs
          - dBZ within [0.0, 75.0]
          - VIL within [0.0, 65.0]
        """
        issues: List[str] = []
        missing: List[str] = []

        if not isinstance(data, dict):
            return ObservationQuality(valid=False, issues=["Data is not a dict"])

        for k in ["dbz_grid", "vil_grid"]:
            if k not in data:
                missing.append(k)

        if missing:
            return ObservationQuality(valid=False, missing_fields=missing, issues=["Missing required grid fields"])

        dbz = data["dbz_grid"]
        vil = data["vil_grid"]

        if not isinstance(dbz, np.ndarray) or not isinstance(vil, np.ndarray):
            return ObservationQuality(valid=False, issues=["Grids are not numpy ndarrays"])

        if dbz.shape != (32, 32) or vil.shape != (32, 32):
            issues.append(f"Invalid grid shape: dbz={dbz.shape}, vil={vil.shape}, expected (32, 32)")

        if np.any(np.isnan(dbz)) or np.any(np.isnan(vil)):
            issues.append("Grids contain NaN values")

        if np.any(np.isinf(dbz)) or np.any(np.isinf(vil)):
            issues.append("Grids contain Inf values")

        out_of_bounds = False
        if np.any(dbz < 0.0) or np.any(dbz > 75.0):
            issues.append(f"dbz values outside [0, 75]: min={np.min(dbz)}, max={np.max(dbz)}")
            out_of_bounds = True

        if np.any(vil < 0.0) or np.any(vil > 65.0):
            issues.append(f"vil values outside [0, 65]: min={np.min(vil)}, max={np.max(vil)}")
            out_of_bounds = True

        score = 1.0 - (0.3 * len(issues))
        score = max(0.0, min(1.0, score))

        return ObservationQuality(
            valid=len(issues) == 0,
            quality_score=score,
            issues=issues,
            out_of_bounds=out_of_bounds,
        )

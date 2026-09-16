"""
Lightning Observation Provider
==============================
Wraps real-time Lightning Detection Network (LDN / Blitzortung) stroke feeds.
Aggregates genuine cloud-to-ground (CG) and intra-cloud (IC) telemetry into spatial density.

Outputs calibrated physical grid:
  - Channel 3: Lightning Flash Density (Flash: [0.0, 25.0] flashes/km²)
  - Flash rate in flashes per minute (fpm) for 2-sigma jump detection.
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
from data_ingestion.lightning_ingest import BlitzortungLightningProvider

logger = logging.getLogger("aerocast.providers.lightning")


class LightningProvider(BaseObservationProvider):
    """
    Live lightning detection provider producing physical (32, 32) flash density grids.
    """

    def __init__(self) -> None:
        super().__init__(name="LightningProvider", source_type="LIGHTNING_LDN")
        self._blitz = BlitzortungLightningProvider()

    async def fetch_latest(
        self,
        lat: float,
        lon: float,
        radius_km: float = 128.0,
        grid_size: int = 32,
        window_minutes: int = 30,
        **kwargs: Any,
    ) -> ProviderResult:
        """
        Fetches strikes in radius, aggregates into (32, 32) flash density grid (flashes/km²).
        """
        t0 = time.perf_counter()
        try:
            strikes = await self._blitz.fetch_lightning_strikes(
                lat=lat,
                lon=lon,
                radius_km=radius_km,
                window_minutes=window_minutes,
            )

            density_grid, flash_rate, meta = self._blitz.calculate_density_grid(
                strikes=strikes,
                center_lat=lat,
                center_lon=lon,
                grid_size=grid_size,
                domain_radius_km=radius_km,
            )

            # Clamp density grid to physical maximum
            density_grid = np.clip(density_grid, 0.0, 25.0).astype(np.float32)

            latency_ms = (time.perf_counter() - t0) * 1000.0

            # Determine latest strike timestamp if available
            obs_time = datetime.now(timezone.utc)
            if strikes:
                latest_epoch = max(
                    [s.get("time", 0) for s in strikes if isinstance(s.get("time"), (int, float))] or [0]
                )
                if latest_epoch > 1_000_000_000:
                    if latest_epoch > 1_000_000_000_000:
                        latest_epoch = latest_epoch / 1000.0
                    obs_time = datetime.fromtimestamp(latest_epoch, tz=timezone.utc)

            freshness, age_minutes = self.get_freshness(obs_time)

            max_dens = float(np.max(density_grid))
            total_flashes = len(strikes)

            data = {
                "flash_density_grid": density_grid,
                "flash_rate_fpm": float(flash_rate),
                "strike_count": total_flashes,
                "max_density": max_dens,
                "active_cells": int(np.sum(density_grid > 0.5)),
            }

            quality = self.validate(data)
            if not quality.valid:
                freshness = "invalid"

            return ProviderResult(
                success=quality.valid,
                data=data,
                timestamp=obs_time,
                latency_ms=latency_ms,
                source="LIVE-BLITZORTUNG-LDN",
                freshness=freshness,
                age_minutes=age_minutes,
                quality=quality,
                error=None,
                metadata={
                    "total_strikes_in_domain": total_flashes,
                    "radius_km": radius_km,
                    "window_minutes": window_minutes,
                    **meta,
                },
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            logger.error("LightningProvider fetch failed: %s", e)
            empty = np.zeros((grid_size, grid_size), dtype=np.float32)
            now = datetime.now(timezone.utc)
            return ProviderResult(
                success=False,
                data={"flash_density_grid": empty, "flash_rate_fpm": 0.0, "strike_count": 0, "max_density": 0.0, "active_cells": 0},
                timestamp=now,
                latency_ms=latency_ms,
                source="ERROR",
                freshness="missing",
                age_minutes=9999.0,
                quality=ObservationQuality(valid=False, issues=[str(e)]),
                error=str(e),
                metadata={"radius_km": radius_km},
            )

    def validate(self, data: Any) -> ObservationQuality:
        """
        Validates lightning density array:
          - Shape must be (32, 32)
          - No NaNs or Infs
          - Density within [0.0, 25.0] flashes/km²
          - Flash rate >= 0.0
        """
        issues: List[str] = []
        missing: List[str] = []

        if not isinstance(data, dict):
            return ObservationQuality(valid=False, issues=["Data is not a dict"])

        for k in ["flash_density_grid", "flash_rate_fpm", "strike_count"]:
            if k not in data:
                missing.append(k)

        if missing:
            return ObservationQuality(valid=False, missing_fields=missing, issues=["Missing required lightning fields"])

        grid = data["flash_density_grid"]
        fpm = data["flash_rate_fpm"]

        if not isinstance(grid, np.ndarray):
            return ObservationQuality(valid=False, issues=["flash_density_grid is not numpy ndarray"])

        if grid.shape != (32, 32):
            issues.append(f"Invalid grid shape: {grid.shape}, expected (32, 32)")

        if np.any(np.isnan(grid)):
            issues.append("flash_density_grid contains NaN values")

        if np.any(np.isinf(grid)):
            issues.append("flash_density_grid contains Inf values")

        out_of_bounds = False
        if np.any(grid < 0.0) or np.any(grid > 25.0):
            issues.append(f"grid density outside [0, 25]: min={np.min(grid)}, max={np.max(grid)}")
            out_of_bounds = True

        if fpm < 0.0:
            issues.append(f"Negative flash rate: {fpm}")
            out_of_bounds = True

        score = 1.0 - (0.3 * len(issues))
        score = max(0.0, min(1.0, score))

        return ObservationQuality(
            valid=len(issues) == 0,
            quality_score=score,
            issues=issues,
            out_of_bounds=out_of_bounds,
        )

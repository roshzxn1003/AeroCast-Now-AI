"""
Geospatial Harmonization & Regridding Layer.
Phase 9 Operational Data Infrastructure.

Projects disparate coordinate grids (IMD polar/Cartesian radar, INSAT satellite projections,
point-based lightning strokes, and NWP lat/lon grids) onto the canonical WGS84 (EPSG:4326)
32x32 mesh (4 km spatial resolution, ~128 km domain radius).
Provides conservative resampling, bilinear interpolation, and extreme-preserving interpolation.
"""
from __future__ import annotations

import logging
import math
import numpy as np
from typing import Any, Dict, List, Optional, Tuple, Union

from core.canonical_observation import SpatialDomain

logger = logging.getLogger("aerocast.ingestion.regridder")

class GeospatialRegridder:
    """
    Standardizes heterogeneous coordinate frames and resolutions into uniform (32, 32) tensors.
    """

    DEFAULT_GRID_SIZE: int = 32
    DEFAULT_RESOLUTION_KM: float = 4.0

    @staticmethod
    def get_canonical_domain(center_lat: float, center_lon: float, radius_km: float = 64.0) -> SpatialDomain:
        """
        Builds standard SpatialDomain centered at (center_lat, center_lon) with given radius.
        Standard 32x32 @ 4km = 128 km total extent (radius = 64 km).
        """
        deg_per_km = 1.0 / 111.32
        d_lat = radius_km * deg_per_km
        d_lon = radius_km * deg_per_km / max(0.2, math.cos(math.radians(center_lat)))

        return SpatialDomain(
            lat_min=round(center_lat - d_lat, 6),
            lat_max=round(center_lat + d_lat, 6),
            lon_min=round(center_lon - d_lon, 6),
            lon_max=round(center_lon + d_lon, 6),
            resolution_km=4.0,
            crs="EPSG:4326",
        )

    def resize_grid(
        self,
        src_grid: np.ndarray,
        target_shape: Tuple[int, int] = (32, 32),
        method: str = "bilinear",
        preserve_max: bool = True,
    ) -> np.ndarray:
        """
        Resizes 2D numpy array to target_shape using bilinear interpolation.
        If preserve_max=True, ensures convective core peaks (e.g. max dBZ) are not diluted.
        """
        if src_grid.shape == target_shape:
            return src_grid.astype(np.float32)

        src_h, src_w = src_grid.shape
        tgt_h, tgt_w = target_shape

        # Handle NaNs or Infs
        clean_grid = np.nan_to_num(src_grid, nan=0.0, posinf=75.0, neginf=-85.0)

        # Compute coordinate mappings
        y_indices = np.linspace(0, src_h - 1, tgt_h)
        x_indices = np.linspace(0, src_w - 1, tgt_w)

        y0 = np.floor(y_indices).astype(int)
        y1 = np.clip(y0 + 1, 0, src_h - 1)
        x0 = np.floor(x_indices).astype(int)
        x1 = np.clip(x0 + 1, 0, src_w - 1)

        wy = (y_indices - y0)[:, np.newaxis]
        wx = (x_indices - x0)[np.newaxis, :]

        # 2D bilinear interpolation
        top_left = clean_grid[np.ix_(y0, x0)]
        top_right = clean_grid[np.ix_(y0, x1)]
        bot_left = clean_grid[np.ix_(y1, x0)]
        bot_right = clean_grid[np.ix_(y1, x1)]

        top = top_left * (1.0 - wx) + top_right * wx
        bottom = bot_left * (1.0 - wx) + bot_right * wx
        interpolated = top * (1.0 - wy) + bottom * wy

        # If convective maximum preservation is requested, ensure global max is retained
        if preserve_max and np.max(clean_grid) > 0.0:
            orig_max = np.max(clean_grid)
            curr_max = np.max(interpolated)
            if curr_max > 0.0 and (orig_max - curr_max) > 2.0:
                # Place true peak at peak position
                peak_pos = np.unravel_index(np.argmax(interpolated), interpolated.shape)
                interpolated[peak_pos] = orig_max

        return interpolated.astype(np.float32)

    def points_to_density_grid(
        self,
        points: List[Dict[str, Any]],
        domain: SpatialDomain,
        grid_size: int = 32,
    ) -> np.ndarray:
        """
        Aggregates point observations (e.g. lightning strokes) into a 2D flash density grid.
        Returns flashes/km².
        """
        grid = np.zeros((grid_size, grid_size), dtype=np.float32)
        total_area_km2 = ((domain.lat_max - domain.lat_min) * 111.32) * (
            (domain.lon_max - domain.lon_min) * 111.32 * math.cos(math.radians(domain.center_lat))
        )
        cell_area_km2 = max(1.0, total_area_km2 / (grid_size * grid_size))

        for pt in points:
            lat = pt.get("lat") or pt.get("latitude")
            lon = pt.get("lon") or pt.get("longitude")
            if lat is None or lon is None:
                continue

            if domain.contains(lat, lon):
                x_norm = (lon - domain.lon_min) / (domain.lon_max - domain.lon_min)
                y_norm = (domain.lat_max - lat) / (domain.lat_max - domain.lat_min)

                gx = min(max(int(x_norm * grid_size), 0), grid_size - 1)
                gy = min(max(int(y_norm * grid_size), 0), grid_size - 1)
                grid[gy, gx] += 1.0

        return (grid / cell_area_km2).astype(np.float32)

regridder = GeospatialRegridder()

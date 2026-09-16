"""
Spatial Grid Regridding & Tensor Mapping
========================================
Maps heterogeneous spatial meteorological observations (radar imagery, satellite
brightness temperatures, and discrete lightning strikes) onto a standard 32 x 32
spatial grid covering the configured study region.

Methods:
  - Bilinear / regular-grid interpolation for continuous fields
  - Exact 2D spatial binning and cell-area normalization for lightning strikes
  - Rigorous missing pixel tracking (NO random filling)
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from scipy.interpolate import RegularGridInterpolator
from PIL import Image

from config.region_config import ACTIVE_REGION, StudyRegionConfig


def calculate_grid_cell_area_km2(region: Optional[StudyRegionConfig] = None) -> float:
    """
    Computes the approximate physical area in km² of a single 32x32 grid cell
    at the centroid latitude of the study region.
    """
    cfg = region or ACTIVE_REGION
    # 1 degree of latitude ≈ 111.13 km
    # 1 degree of longitude ≈ 111.32 * cos(latitude) km
    lat_km = ((cfg.max_lat - cfg.min_lat) * 111.13) / cfg.grid_size
    mean_lat_rad = math.radians(cfg.center_lat)
    lon_km = ((cfg.max_lon - cfg.min_lon) * 111.32 * math.cos(mean_lat_rad)) / cfg.grid_size
    return float(max(0.1, lat_km * lon_km))


def regrid_to_32x32(
    data: np.ndarray,
    src_lats: Optional[np.ndarray] = None,
    src_lons: Optional[np.ndarray] = None,
    region: Optional[StudyRegionConfig] = None,
    fill_value: Optional[float] = None,
    interpolation_method: str = "bilinear"
) -> Tuple[np.ndarray, float]:
    """
    Regrids a 2D physical field onto the canonical (32, 32) spatial grid.

    Args:
        data: 2D source array (H_in, W_in)
        src_lats: 1D array of source latitudes (sorted ascending), optional
        src_lons: 1D array of source longitudes (sorted ascending), optional
        region: Target StudyRegionConfig (defaults to ACTIVE_REGION)
        fill_value: Value for unobserved cells outside source domain (or None to keep NaN)
        interpolation_method: 'bilinear' or 'nearest'

    Returns:
        regridded: 2D array of shape (32, 32)
        missing_pct: Fraction of cells that were unobserved / NaN (0.0 to 100.0)
    """
    cfg = region or ACTIVE_REGION
    target_size = cfg.grid_size  # 32

    # Case 1: Simple 2D array without explicit lat/lon coordinates (e.g. radar image crop)
    # Use high-quality PIL bilinear resampling
    if src_lats is None or src_lons is None:
        if data.shape == (target_size, target_size):
            out = data.astype(np.float32)
        else:
            # Handle NaN values safely before PIL resize
            nan_mask = np.isnan(data)
            temp = np.nan_to_num(data, nan=0.0)
            img = Image.fromarray(temp.astype(np.float32))
            resample_mode = Image.Resampling.BILINEAR if interpolation_method == "bilinear" else Image.Resampling.NEAREST
            resized = img.resize((target_size, target_size), resample=resample_mode)
            out = np.array(resized, dtype=np.float32)
            
            # Propagate NaN mask to target size
            if np.any(nan_mask):
                mask_img = Image.fromarray(nan_mask.astype(np.uint8) * 255)
                mask_resized = np.array(mask_img.resize((target_size, target_size), resample=Image.Resampling.NEAREST)) > 128
                out[mask_resized] = np.nan

        missing_pct = float(np.mean(np.isnan(out)) * 100.0)
        if fill_value is not None:
            out = np.nan_to_num(out, nan=fill_value)
        return out, missing_pct

    # Case 2: Source coordinates provided (e.g. Gridded satellite / reanalysis dataset)
    # Ensure source coordinate arrays are strictly ascending for RegularGridInterpolator
    if src_lats[0] > src_lats[-1]:
        src_lats = src_lats[::-1]
        data = data[::-1, :]
    if src_lons[0] > src_lons[-1]:
        src_lons = src_lons[::-1]
        data = data[:, ::-1]

    # Build target grid coordinate evaluation points
    tgt_lats = np.linspace(cfg.min_lat, cfg.max_lat, target_size)
    tgt_lons = np.linspace(cfg.min_lon, cfg.max_lon, target_size)
    grid_lat, grid_lon = np.meshgrid(tgt_lats, tgt_lons, indexing='ij')

    # Fit regular grid interpolator
    interp = RegularGridInterpolator(
        (src_lats, src_lons),
        data,
        method="linear" if interpolation_method == "bilinear" else "nearest",
        bounds_error=False,
        fill_value=np.nan
    )

    pts = np.stack([grid_lat.ravel(), grid_lon.ravel()], axis=-1)
    regridded_flat = interp(pts)
    regridded = regridded_flat.reshape((target_size, target_size)).astype(np.float32)

    missing_pct = float(np.mean(np.isnan(regridded)) * 100.0)
    if fill_value is not None:
        regridded = np.nan_to_num(regridded, nan=fill_value)

    return regridded, missing_pct


def regrid_lightning_strikes(
    strikes: List[Dict[str, Any]],
    region: Optional[StudyRegionConfig] = None
) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    Bins point lightning stroke records into 32x32 spatial cells:
      - lightning_count: Number of flashes per cell (integer count)
      - lightning_density: Flashes per km² (count / cell_area_km2)
      - total_flashes: Total valid strokes inside the study domain

    Args:
        strikes: List of dicts with 'lat' and 'lon' keys
        region: Target StudyRegionConfig

    Returns:
        count_grid: Shape (32, 32) float32
        density_grid: Shape (32, 32) float32 (flashes/km²)
        total_flashes: Total strikes recorded in domain
    """
    cfg = region or ACTIVE_REGION
    grid_size = cfg.grid_size
    cell_area_km2 = calculate_grid_cell_area_km2(cfg)

    count_grid = np.zeros((grid_size, grid_size), dtype=np.float32)

    if not strikes:
        return count_grid, count_grid.copy(), 0.0

    lats: List[float] = []
    lons: List[float] = []
    for s in strikes:
        lat = s.get("lat") or s.get("latitude")
        lon = s.get("lon") or s.get("longitude")
        if lat is not None and lon is not None:
            if cfg.contains_point(float(lat), float(lon)):
                lats.append(float(lat))
                lons.append(float(lon))

    total_flashes = float(len(lats))
    if total_flashes > 0:
        lat_bins = np.linspace(cfg.min_lat, cfg.max_lat, grid_size + 1)
        lon_bins = np.linspace(cfg.min_lon, cfg.max_lon, grid_size + 1)
        
        # 2D Histogram: rows correspond to latitude bins, columns to longitude bins
        h, _, _ = np.histogram2d(lats, lons, bins=[lat_bins, lon_bins])
        count_grid = h.astype(np.float32)

    density_grid = (count_grid / cell_area_km2).astype(np.float32)
    return count_grid, density_grid, total_flashes


def check_missing_pixels(grid: np.ndarray) -> float:
    """Returns the percentage of missing (NaN or infinite) values in a grid."""
    if grid.size == 0:
        return 100.0
    nan_count = np.sum(np.isnan(grid) | np.isinf(grid))
    return float((nan_count / grid.size) * 100.0)


def build_4channel_spatial_frame(
    dbz_grid: np.ndarray,
    vil_grid: np.ndarray,
    tir_grid: np.ndarray,
    flash_density_grid: np.ndarray
) -> np.ndarray:
    """
    Stacks 4 calibrated 2D fields into an unnormalized (32, 32, 4) physical array:
      - Channel 0: Radar Reflectivity (dBZ: [0, 75])
      - Channel 1: Vertically Integrated Liquid (VIL: [0, 65] kg/m²)
      - Channel 2: Satellite TIR Brightness Temp (°C: [-85, +35])
      - Channel 3: Lightning Flash Density (flashes/km²: [0, 25])
    """
    assert dbz_grid.shape == (32, 32), f"Expected (32, 32), got {dbz_grid.shape}"
    assert vil_grid.shape == (32, 32), f"Expected (32, 32), got {vil_grid.shape}"
    assert tir_grid.shape == (32, 32), f"Expected (32, 32), got {tir_grid.shape}"
    assert flash_density_grid.shape == (32, 32), f"Expected (32, 32), got {flash_density_grid.shape}"

    return np.stack([
        dbz_grid.astype(np.float32),
        vil_grid.astype(np.float32),
        tir_grid.astype(np.float32),
        flash_density_grid.astype(np.float32)
    ], axis=-1)

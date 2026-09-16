"""
Meteorological Target Definition & Labeling
===========================================
Defines objective, physically grounded ground-truth targets for thunderstorm and
lightning nowcasting:

1. Lightning Targets:
   - Cell-level 32x32 flash density (flashes/km²) at T0, T+15, T+30, T+45, T+60
   - Grid-wide total flash count and binary lightning occurrence flag (flashes > 0)

2. Thunderstorm Target:
   - Binary thunderstorm occurrence indicator:
       0 = No thunderstorm (Clear air, fog, or light stratiform precipitation)
       1 = Thunderstorm (Deep convective storm with active lightning / heavy core)
   - Exact physical threshold rule:
       thunderstorm = 1 IF:
         (Max Radar Reflectivity >= 35.0 dBZ) OR
         (Total Lightning Flash Count >= 1 in 15-min window) OR
         (Max Vertically Integrated Liquid (VIL) >= 15.0 kg/m²)
       ELSE:
         thunderstorm = 0
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple
import numpy as np

# Standard meteorological convective thresholds
THUNDERSTORM_DBZ_THRESHOLD = 35.0        # dBZ: initiation of deep convective storm cores
THUNDERSTORM_VIL_THRESHOLD = 15.0        # kg/m²: high liquid content / potential severe hail
THUNDERSTORM_FLASH_THRESHOLD = 1.0       # Minimum flash count inside domain in 15 minutes
LIGHTNING_FLASH_DENSITY_THRESHOLD = 0.05 # flashes/km²: detectable lightning density


def compute_thunderstorm_target(
    dbz_grid: np.ndarray,
    vil_grid: np.ndarray,
    flash_grid: np.ndarray
) -> Tuple[int, float, Dict[str, Any]]:
    """
    Computes objective binary thunderstorm target and convective severity score
    for a single 32x32 spatial grid timestamp.

    Args:
        dbz_grid: Unnormalized radar reflectivity in dBZ (32, 32)
        vil_grid: Unnormalized VIL in kg/m² (32, 32)
        flash_grid: Unnormalized lightning flash density in flashes/km² (32, 32)

    Returns:
        is_thunderstorm: Binary 0 or 1
        convective_severity_score: Continuous index [0.0, 1.0]
        metrics: Dictionary with observed maxima and trigger flags
    """
    max_dbz = float(np.nanmax(dbz_grid)) if dbz_grid.size > 0 else 0.0
    max_vil = float(np.nanmax(vil_grid)) if vil_grid.size > 0 else 0.0
    max_flash = float(np.nanmax(flash_grid)) if flash_grid.size > 0 else 0.0
    valid_flashes = flash_grid[flash_grid >= LIGHTNING_FLASH_DENSITY_THRESHOLD]
    sum_flash = float(np.nansum(valid_flashes)) if valid_flashes.size > 0 else 0.0

    radar_trigger = max_dbz >= THUNDERSTORM_DBZ_THRESHOLD
    vil_trigger = max_vil >= THUNDERSTORM_VIL_THRESHOLD
    lightning_trigger = (max_flash >= LIGHTNING_FLASH_DENSITY_THRESHOLD) or (sum_flash >= THUNDERSTORM_FLASH_THRESHOLD)

    is_thunderstorm = 1 if (radar_trigger or vil_trigger or lightning_trigger) else 0

    # Continuous severity score [0.0 to 1.0]
    dbz_score = np.clip((max_dbz - 20.0) / 45.0, 0.0, 1.0)
    vil_score = np.clip(max_vil / 40.0, 0.0, 1.0)
    flash_score = np.clip(max_flash / 10.0, 0.0, 1.0)

    # Convective severity is max of multi-modal indicators with core weighting
    severity = float(np.clip(0.4 * dbz_score + 0.3 * vil_score + 0.3 * flash_score, 0.0, 1.0))

    metrics = {
        "max_dbz": round(max_dbz, 2),
        "max_vil": round(max_vil, 2),
        "max_flash_density": round(max_flash, 3),
        "sum_flash_density": round(sum_flash, 3),
        "radar_trigger": bool(radar_trigger),
        "vil_trigger": bool(vil_trigger),
        "lightning_trigger": bool(lightning_trigger),
        "is_thunderstorm": is_thunderstorm,
        "severity_score": round(severity, 3),
    }

    return is_thunderstorm, severity, metrics


def compute_lightning_targets(
    sequence_spatial_frames: np.ndarray,
    input_steps: int = 4,
    forecast_steps: int = 4
) -> Dict[str, Any]:
    """
    Extracts multi-horizon ground-truth lightning targets across an 8-step sequence:
      - T0 (current)
      - T+15, T+30, T+45, T+60 (future forecast steps)

    Args:
        sequence_spatial_frames: Unnormalized or normalized array of shape (8, 32, 32, 4)
                                 Channel 3 is Lightning Flash Density.

    Returns:
        targets: Dictionary containing:
          - 't0_grid': (32, 32)
          - 't15_grid': (32, 32)
          - 't30_grid': (32, 32)
          - 't45_grid': (32, 32)
          - 't60_grid': (32, 32)
          - 'future_lightning_grids': (4, 32, 32)
          - 'future_binary_lightning': (4,) array (1 if any flash in future step)
          - 'future_max_density': (4,) array
    """
    assert len(sequence_spatial_frames) >= (input_steps + forecast_steps)

    # Flash density is Channel 3
    flash_seq = sequence_spatial_frames[:, :, :, 3]

    t0_idx = input_steps - 1  # index 3
    t0_grid = flash_seq[t0_idx]

    future_grids = flash_seq[input_steps : input_steps + forecast_steps]  # steps 4, 5, 6, 7

    future_binary = np.array([
        1 if np.nanmax(future_grids[step]) >= LIGHTNING_FLASH_DENSITY_THRESHOLD else 0
        for step in range(forecast_steps)
    ], dtype=np.int32)

    future_max = np.array([
        float(np.nanmax(future_grids[step]))
        for step in range(forecast_steps)
    ], dtype=np.float32)

    return {
        "t0_grid": t0_grid,
        "t15_grid": future_grids[0],
        "t30_grid": future_grids[1],
        "t45_grid": future_grids[2],
        "t60_grid": future_grids[3],
        "future_lightning_grids": future_grids,
        "future_binary_lightning": future_binary,
        "future_max_density": future_max,
    }

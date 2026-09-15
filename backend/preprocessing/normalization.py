"""
Channel Normalization & Scaling
===============================
Standardizes multi-modal physical variables to [0.0, 1.0] for ConvLSTM2D input:
  - Channel 0: Doppler Reflectivity (dBZ: [0, 75] -> [0, 1])
  - Channel 1: Vertically Integrated Liquid (VIL: [0, 65] kg/m² -> [0, 1])
  - Channel 2: INSAT-3D Thermal IR (TIR: [-85, +35] °C -> [0, 1], cold tops = 1.0)
  - Channel 3: Lightning Density (Flash: [0, 25] flashes/km² -> [0, 1])

Includes inverse scaling functions for prediction denormalization.
"""

from __future__ import annotations

import numpy as np


# Operational physical extrema
DBZ_MAX = 75.0
VIL_MAX = 65.0
TIR_GROUND_C = 35.0
TIR_RANGE_C = 120.0  # -85°C to +35°C
FLASH_DENSITY_MAX = 25.0


def normalize_channels(
    dbz: np.ndarray,
    vil: np.ndarray,
    tir: np.ndarray,
    flash: np.ndarray
) -> np.ndarray:
    """
    Stacks and normalizes 4 2D physical grids into a 3D (H, W, 4) float32 tensor
    with all channels scaled to [0.0, 1.0].
    """
    norm_dbz = np.clip(dbz / DBZ_MAX, 0.0, 1.0).astype(np.float32)
    norm_vil = np.clip(vil / VIL_MAX, 0.0, 1.0).astype(np.float32)
    # Cold cloud tops (e.g. -70°C) map close to 1.0; warm ground (e.g. 30°C) maps close to 0.0
    norm_tir = np.clip((TIR_GROUND_C - tir) / TIR_RANGE_C, 0.0, 1.0).astype(np.float32)
    norm_flash = np.clip(flash / FLASH_DENSITY_MAX, 0.0, 1.0).astype(np.float32)

    return np.stack([norm_dbz, norm_vil, norm_tir, norm_flash], axis=-1)


def denormalize_dbz(norm_dbz: np.ndarray) -> np.ndarray:
    """Restores normalized channel 0 back to physical dBZ."""
    return np.clip(norm_dbz * DBZ_MAX, 0.0, DBZ_MAX).astype(np.float32)


def denormalize_vil(norm_vil: np.ndarray) -> np.ndarray:
    """Restores normalized channel 1 back to physical VIL (kg/m²)."""
    return np.clip(norm_vil * VIL_MAX, 0.0, VIL_MAX).astype(np.float32)


def denormalize_tir(norm_tir: np.ndarray) -> np.ndarray:
    """Restores normalized channel 2 back to physical Brightness Temperature (°C)."""
    return np.clip(TIR_GROUND_C - (norm_tir * TIR_RANGE_C), -85.0, TIR_GROUND_C).astype(np.float32)


def denormalize_flash(norm_flash: np.ndarray) -> np.ndarray:
    """Restores normalized channel 3 back to physical flash density (flashes/km²)."""
    return np.clip(norm_flash * FLASH_DENSITY_MAX, 0.0, FLASH_DENSITY_MAX).astype(np.float32)

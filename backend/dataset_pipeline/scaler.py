"""
Multi-Modal Channel Normalization & Scaler Persistence
======================================================
Fits normalization parameters EXCLUSIVELY on the training split (X_train)
and preserves physical scaling constants for validation, test, and production:

  - Channel 0: Radar Reflectivity (dBZ: [0, 75] -> [0, 1])
  - Channel 1: Vertically Integrated Liquid (VIL: [0, 65] kg/m² -> [0, 1])
  - Channel 2: INSAT-3D Thermal IR (TIR: [-85, +35] °C -> [0, 1], cold tops = 1.0)
  - Channel 3: Lightning Flash Density (Flash: [0, 25] flashes/km² -> [0, 1])

Saves fitted scaler to:
  data/processed/scaler.pkl
  data/processed/scaler_params.json
"""

from __future__ import annotations

import json
import os
import pickle
from typing import Any, Dict, Optional, Tuple, Union
import numpy as np


class ChannelScaler:
    """
    Normalizes multi-modal 4D spatio-temporal arrays.
    Strictly fit on training data only to avoid temporal data leakage.
    """

    def __init__(
        self,
        dbz_max: float = 75.0,
        vil_max: float = 65.0,
        tir_ground_c: float = 35.0,
        tir_range_c: float = 120.0,
        flash_max: float = 25.0
    ) -> None:
        self.dbz_max = float(dbz_max)
        self.vil_max = float(vil_max)
        self.tir_ground_c = float(tir_ground_c)
        self.tir_range_c = float(tir_range_c)
        self.flash_max = float(flash_max)
        
        self.is_fitted = False
        self.fit_metadata: Dict[str, Any] = {}

    def fit(self, X_train: np.ndarray) -> ChannelScaler:
        """
        Fits empirical distributions and confirms bounds exclusively on training set.
        
        Args:
            X_train: Array of shape (N_train, T, H, W, C=4) or (N_train, H, W, C=4)
        """
        assert X_train.ndim in (4, 5), f"Expected 4D or 5D array, got ndim={X_train.ndim}"
        assert X_train.shape[-1] == 4, f"Expected 4 channels, got {X_train.shape[-1]}"

        # Flatten spatial dimensions per channel
        ch0 = X_train[..., 0]
        ch1 = X_train[..., 1]
        ch2 = X_train[..., 2]
        ch3 = X_train[..., 3]

        def _stats(arr: np.ndarray) -> Dict[str, float]:
            v = arr[~np.isnan(arr)]
            if len(v) == 0:
                return {"min": 0.0, "max": 1.0, "mean": 0.0, "std": 1.0, "p99": 1.0}
            return {
                "min": float(np.min(v)),
                "max": float(np.max(v)),
                "mean": float(np.mean(v)),
                "std": float(np.std(v)),
                "p99": float(np.percentile(v, 99.0)),
            }

        self.fit_metadata = {
            "num_training_samples": int(X_train.shape[0]),
            "channel_0_dbz": _stats(ch0),
            "channel_1_vil": _stats(ch1),
            "channel_2_tir": _stats(ch2),
            "channel_3_flash": _stats(ch3),
            "scaling_constants": {
                "dbz_max": self.dbz_max,
                "vil_max": self.vil_max,
                "tir_ground_c": self.tir_ground_c,
                "tir_range_c": self.tir_range_c,
                "flash_max": self.flash_max,
            }
        }
        self.is_fitted = True
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        """
        Scales physical variables to [0.0, 1.0].
        
        Channel 0 (Radar dBZ):      [0, 75]    -> [0, 1]
        Channel 1 (VIL):            [0, 65]    -> [0, 1]
        Channel 2 (Satellite TIR):  [-85, +35] -> [0, 1] (cold cloud top = 1.0)
        Channel 3 (Lightning):      [0, 25]    -> [0, 1]
        """
        assert X.shape[-1] == 4, f"Expected last dimension to be 4 channels, got {X.shape[-1]}"
        out = np.zeros_like(X, dtype=np.float32)

        # Channel 0: dBZ
        out[..., 0] = np.clip(X[..., 0] / self.dbz_max, 0.0, 1.0)
        # Channel 1: VIL
        out[..., 1] = np.clip(X[..., 1] / self.vil_max, 0.0, 1.0)
        # Channel 2: Satellite TIR (cold cloud tops e.g. -70°C map to (35 - (-70))/120 = 105/120 ≈ 0.88)
        out[..., 2] = np.clip((self.tir_ground_c - X[..., 2]) / self.tir_range_c, 0.0, 1.0)
        # Channel 3: Lightning Flash Density
        out[..., 3] = np.clip(X[..., 3] / self.flash_max, 0.0, 1.0)

        return np.nan_to_num(out, nan=0.0)

    def inverse_transform(self, X_norm: np.ndarray) -> np.ndarray:
        """
        Converts normalized [0.0, 1.0] tensor back to physical variables.
        """
        assert X_norm.shape[-1] == 4, f"Expected last dimension to be 4 channels, got {X_norm.shape[-1]}"
        out = np.zeros_like(X_norm, dtype=np.float32)

        out[..., 0] = np.clip(X_norm[..., 0] * self.dbz_max, 0.0, self.dbz_max)
        out[..., 1] = np.clip(X_norm[..., 1] * self.vil_max, 0.0, self.vil_max)
        out[..., 2] = np.clip(self.tir_ground_c - (X_norm[..., 2] * self.tir_range_c), self.tir_ground_c - self.tir_range_c, self.tir_ground_c)
        out[..., 3] = np.clip(X_norm[..., 3] * self.flash_max, 0.0, self.flash_max)

        return out

    def save(self, filepath: str) -> None:
        """Saves scaler to pickle and creates human-readable JSON parameters next to it."""
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "wb") as f:
            pickle.dump(self, f)

        json_path = os.path.splitext(filepath)[0] + "_params.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.fit_metadata, f, indent=2)

    @classmethod
    def load(cls, filepath: str) -> ChannelScaler:
        """Loads scaler from pickle file."""
        with open(filepath, "rb") as f:
            scaler = pickle.load(f)
        if not isinstance(scaler, cls):
            raise TypeError(f"Loaded object is {type(scaler)}, expected {cls}")
        return scaler

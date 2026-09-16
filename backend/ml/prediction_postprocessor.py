"""
Prediction Postprocessor
========================
Processes raw multi-modal ConvLSTM output tensors into physical meteorological products:
  1. Inverse channel scaling using ChannelScaler (dBZ, VIL, TIR, Flash).
  2. Spatio-temporal SCIT / TITAN storm cell tracking & centroid vector derivation.
  3. Severe thunderstorm hazard scoring and 2-sigma lightning jump detection.
  4. Common Alerting Protocol (CAP v1.2) XML/JSON alert bulletin formatting.
  5. Compact downsampled coordinate heatmaps for real-time 3D Earth globe rendering.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from dataset_pipeline.scaler import ChannelScaler
from nowcasting_engine import (
    identify_and_track_storm_cells,
    detect_lightning_jump,
    generate_cap_bulletin,
)
from observation_service import generate_lightning_jump_timeseries

logger = logging.getLogger("aerocast.ml.postprocessor")


def grid_to_heatmap(grid: np.ndarray, downsample: int = 2) -> List[Dict[str, Any]]:
    """
    Converts a 2D numpy grid to a sparse list of {y, x, v} points
    for efficient frontend heatmap rendering on 2D radar and 3D globe.
    """
    h, w = grid.shape
    points = []
    for y in range(0, h, downsample):
        for x in range(0, w, downsample):
            val = float(grid[y, x])
            if val > 0.5:  # Skip near-zero background clear air
                points.append({
                    "y": y,
                    "x": x,
                    "v": round(val, 1),
                })
    return points


class PredictionPostprocessor:
    """
    Post-processes normalized ConvLSTM forecast tensors into domain-specific nowcast alerts.
    """

    def __init__(self, scaler: ChannelScaler) -> None:
        self.scaler = scaler

    def process_forecast(
        self,
        forecast_norm: np.ndarray,
        history_physical: np.ndarray,
        sounding_params: Dict[str, Any],
        station_name: str,
        observation_timestamp: datetime,
        forecast_steps: int = 4,
    ) -> Dict[str, Any]:
        """
        Takes:
          - forecast_norm: (forecast_steps, 32, 32, 4) in [0.0, 1.0]
          - history_physical: (4, 32, 32, 4) in physical units
          - sounding_params: Convective instability metrics
          - station_name: Station identifier
          - observation_timestamp: Timestamp of T0
        Returns:
          - observation dictionary
          - forecast steps list
          - forecast grids list
          - lightning jump analysis
          - CAP bulletin
        """
        assert forecast_norm.ndim == 4, f"Expected 4D array, got {forecast_norm.shape}"
        assert history_physical.ndim == 4, f"Expected 4D array, got {history_physical.shape}"

        # 1. Inverse transform normalized predictions back to physical units
        forecast_physical = self.scaler.inverse_transform(forecast_norm)

        # 2. Extract last observed frame (T_0)
        last_obs = history_physical[-1]
        last_dbz = last_obs[..., 0]
        last_vil = last_obs[..., 1]
        last_tir = last_obs[..., 2]
        last_fl = last_obs[..., 3]

        obs_cells = identify_and_track_storm_cells(last_dbz, last_vil)

        # Format historical frames (-45, -30, -15, 0 min)
        history_offsets = [-45, -30, -15, 0]
        history_grids = []
        n_hist = history_physical.shape[0]
        for i in range(n_hist):
            offset = history_offsets[i] if i < len(history_offsets) else (i - n_hist + 1) * 15
            history_grids.append({
                "offset_min": offset,
                "dbz": grid_to_heatmap(history_physical[i, ..., 0], downsample=2),
                "vil": grid_to_heatmap(history_physical[i, ..., 1], downsample=2),
            })

        # 3. Forecast steps (+15, +30, +45, +60 min)
        lead_times = [15, 30, 45, 60, 90, 120]
        forecast_cells_by_step = []
        forecast_grids = []

        total_steps = min(forecast_steps, forecast_physical.shape[0])
        for step_idx in range(total_steps):
            fc_dbz = forecast_physical[step_idx, ..., 0]
            fc_vil = forecast_physical[step_idx, ..., 1]
            fc_tir = forecast_physical[step_idx, ..., 2]
            fc_flash = forecast_physical[step_idx, ..., 3]

            lead_min = lead_times[step_idx] if step_idx < len(lead_times) else (step_idx + 1) * 15
            cells = identify_and_track_storm_cells(fc_dbz, fc_vil)

            max_fc_dbz = float(np.max(fc_dbz))
            max_fc_vil = float(np.max(fc_vil))
            min_fc_tir = float(np.min(fc_tir))
            tot_fc_flash = float(np.sum(fc_flash) * 0.4)

            forecast_cells_by_step.append({
                "lead_time_min": lead_min,
                "cells": cells,
                "max_dbz": max_fc_dbz,
                "max_vil": max_fc_vil,
                "min_tir_c": min_fc_tir,
                "total_flash_rate": tot_fc_flash,
            })

            forecast_grids.append({
                "lead_time_min": lead_min,
                "dbz": grid_to_heatmap(fc_dbz, downsample=2),
                "vil": grid_to_heatmap(fc_vil, downsample=2),
            })

        # 4. Lightning Jump analysis
        has_storm = float(np.max(last_dbz)) >= 35.0 or float(np.max(last_fl)) >= 3.0
        flash_df = generate_lightning_jump_timeseries(
            duration_mins=75, interval_mins=5, has_jump=has_storm
        )
        jump_result = detect_lightning_jump(flash_df)

        # 5. CAP Alert Bulletin
        cap_bulletin = generate_cap_bulletin(
            station_name=station_name,
            storm_cells=obs_cells,
            jump_info=jump_result,
            sounding=sounding_params,
        )

        observation_payload = {
            "max_dbz": float(np.max(last_dbz)),
            "max_vil": float(np.max(last_vil)),
            "min_tir_c": float(np.min(last_tir)),
            "flash_rate_fpm": float(np.sum(last_fl) * 0.4),
            "storm_cells": obs_cells,
            "dbz_grid": grid_to_heatmap(last_dbz, downsample=2),
            "history_grids": history_grids,
        }

        return {
            "observation": observation_payload,
            "forecast": forecast_cells_by_step,
            "forecast_grids": forecast_grids,
            "lightning_jump": jump_result,
            "cap_bulletin": cap_bulletin,
        }

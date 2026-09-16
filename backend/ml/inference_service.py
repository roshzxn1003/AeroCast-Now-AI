"""
Live Machine Learning Nowcasting Inference Service
==================================================
Runs real-time ConvLSTM spatio-temporal inference over synchronized 4-frame multi-modal sequences:
  - Input:  (4, 32, 32, 4) physical tensor normalized via ChannelScaler -> (1, 4, 32, 32, 4)
  - Model:  Residual-Attention ConvLSTM2D (Phase 3 best model: convlstm_real_best.keras)
  - Output: (1, 4, 32, 32, 4) normalized predictions (+15, +30, +45, +60 min)
  - Postprocessing: SCIT storm cell tracking, 2-sigma lightning jump, CAP alert bulletins
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ml.model_loader import ModelLoader
from ml.prediction_postprocessor import PredictionPostprocessor

logger = logging.getLogger("aerocast.ml.inference")


class LiveInferenceService:
    """
    End-to-end inference service managing model execution, normalization, and alert generation.
    """

    def __init__(self, model_mode: Optional[str] = None) -> None:
        self.model_mode = model_mode or os.getenv("MODEL_MODE", "real")
        self.model, self.model_meta = ModelLoader.get_model(mode=self.model_mode)
        self.scaler = ModelLoader.get_scaler()
        self.postprocessor = PredictionPostprocessor(scaler=self.scaler)

    def run_prediction(
        self,
        sequence_physical: np.ndarray,
        sounding_params: Dict[str, Any],
        station_name: str = "Chennai DWR (Sriharikota/Port)",
        observation_timestamp: Optional[datetime] = None,
        forecast_steps: int = 4,
        provenance: str = "LIVE_REAL_DATA",
        mode: str = "real",
        freshness: Optional[Any] = None,
        data_note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes ConvLSTM inference and formats full meteorological nowcast response.
        """
        assert sequence_physical.ndim == 4, f"Expected (4, 32, 32, 4) tensor, got {sequence_physical.shape}"
        assert sequence_physical.shape == (4, 32, 32, 4), f"Sequence shape must be (4, 32, 32, 4), got {sequence_physical.shape}"

        obs_time = observation_timestamp or datetime.now(timezone.utc)
        if obs_time.tzinfo is None:
            obs_time = obs_time.replace(tzinfo=timezone.utc)

        t0 = time.perf_counter()

        # 1. Scale physical inputs to [0.0, 1.0] using fitted ChannelScaler
        scaled_input = self.scaler.transform(sequence_physical)  # (4, 32, 32, 4)
        batch_input = np.expand_dims(scaled_input, axis=0)        # (1, 4, 32, 32, 4)

        # 2. Run ConvLSTM neural network inference
        raw_pred = self.model.predict(batch_input, verbose=0)     # (1, 4, 32, 32, 4)
        forecast_norm = raw_pred[0]                              # (4, 32, 32, 4)

        # 3. Handle multi-step autoregression if forecast_steps > 4 (e.g. +90, +120 min)
        if forecast_steps > 4:
            ext_steps = forecast_steps - 4
            extended_preds = list(forecast_norm)
            curr_input = batch_input.copy()

            for _ in range(ext_steps):
                roll_in = np.concatenate([curr_input[:, 1:, ...], raw_pred[:, -1:, ...]], axis=1)
                next_pred = self.model.predict(roll_in, verbose=0)
                extended_preds.append(next_pred[0, -1])
                curr_input = roll_in
                raw_pred = next_pred

            forecast_norm = np.stack(extended_preds[:forecast_steps], axis=0)

        inference_time_ms = (time.perf_counter() - t0) * 1000.0

        # 4. Post-process into meteorological nowcast products
        processed = self.postprocessor.process_forecast(
            forecast_norm=forecast_norm[:forecast_steps],
            history_physical=sequence_physical,
            sounding_params=sounding_params,
            station_name=station_name,
            observation_timestamp=obs_time,
            forecast_steps=forecast_steps,
        )

        pred_time = datetime.now(timezone.utc)

        # Resolve clean data note
        if not data_note:
            if "LIVE" in provenance:
                note = f"LIVE DATA — Authentic IMD Radar + INSAT-3D Satellite ({provenance})"
            elif "HYBRID" in provenance:
                note = f"HYBRID DATA — Real-world radar/satellite observations aligned with active convective background."
            else:
                note = "SIMULATED DATA — Synthetic convective scenario."
        else:
            note = data_note

        freshness_payload = freshness.to_dict() if hasattr(freshness, "to_dict") else (freshness or {})

        return {
            "mode": mode,
            "provenance": provenance,
            "data_note": note,
            "sequence_ready": True,
            "station": station_name,
            "observation_timestamp": obs_time.isoformat(),
            "prediction_timestamp": pred_time.isoformat(),
            "inference_time_ms": round(inference_time_ms, 1),
            "freshness": freshness_payload,
            "observation": processed["observation"],
            "forecast": processed["forecast"],
            "forecast_grids": processed["forecast_grids"],
            "lightning_jump": processed["lightning_jump"],
            "cap_bulletin": processed["cap_bulletin"],
            "sounding": sounding_params,
            "model_metadata": {
                "active_checkpoint": os.path.basename(self.model_meta.get("checkpoint_path", "convlstm_real_best.keras")),
                "active_mode": self.model_mode,
                "parameter_count": self.model_meta.get("parameter_count", self.model.count_params()),
            }
        }

"""
Machine Learning Model Loader
=============================
Singleton manager for loading and caching the ConvLSTM nowcasting model and ChannelScaler:
  - Real Model Checkpoint: backend/models/convlstm_real_best.keras (Phase 3 best model)
  - Synthetic Baseline:    backend/models/convlstm_nowcaster.keras
  - Fitted Scaler:         data/processed/scaler.pkl (ChannelScaler)
"""

from __future__ import annotations

import json
import logging
import os
import pickle
import threading
from typing import Any, Dict, Optional, Tuple

import tensorflow as tf

from dataset_pipeline.scaler import ChannelScaler
from nowcasting_engine import weighted_convective_loss

logger = logging.getLogger("aerocast.ml.loader")

_lock = threading.Lock()
_cached_model: Optional[tf.keras.Model] = None
_cached_scaler: Optional[ChannelScaler] = None
_cached_metadata: Optional[Dict[str, Any]] = None
_active_mode: str = "real"


class ModelLoader:
    """
    Thread-safe singleton model and scaler loader.
    """

    @classmethod
    def get_model(cls, mode: Optional[str] = None) -> Tuple[tf.keras.Model, Dict[str, Any]]:
        """
        Retrieves the compiled ConvLSTM model instance.
        """
        global _cached_model, _cached_metadata, _active_mode
        requested_mode = (mode or os.getenv("MODEL_MODE", "real")).lower()

        with _lock:
            if _cached_model is not None and _active_mode == requested_mode:
                return _cached_model, _cached_metadata or {}

            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            models_dir = os.path.join(base_dir, "models")

            real_path = os.path.join(models_dir, "convlstm_real_best.keras")
            real_meta = os.path.join(models_dir, "model_metadata_real.json")
            syn_path = os.path.join(models_dir, "convlstm_nowcaster.keras")
            syn_meta = os.path.join(models_dir, "model_metadata.json")

            if requested_mode in ("real", "live") and os.path.exists(real_path):
                target_path = real_path
                meta_path = real_meta if os.path.exists(real_meta) else syn_meta
                active_mode = "real"
            elif os.path.exists(syn_path):
                target_path = syn_path
                meta_path = syn_meta
                active_mode = "simulation"
            elif os.path.exists(real_path):
                target_path = real_path
                meta_path = real_meta
                active_mode = "real"
            else:
                raise FileNotFoundError(f"No trained model checkpoints found in {models_dir}")

            logger.info("Loading ConvLSTM weights from %s (mode=%s)...", target_path, active_mode)
            try:
                model = tf.keras.models.load_model(
                    target_path,
                    custom_objects={"weighted_convective_loss": weighted_convective_loss},
                    compile=False,
                )
            except Exception as e:
                logger.warning("Custom object load failed (%s), loading with standard compile=False", e)
                model = tf.keras.models.load_model(target_path, compile=False)

            model.compile(loss=weighted_convective_loss, metrics=["mae"])

            metadata: Dict[str, Any] = {}
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        metadata = json.load(f)
                except Exception as exc:
                    logger.warning("Could not read metadata from %s: %s", meta_path, exc)

            metadata["checkpoint_path"] = target_path
            metadata["active_mode"] = active_mode
            metadata["parameter_count"] = model.count_params()

            _cached_model = model
            _cached_metadata = metadata
            _active_mode = active_mode

            return _cached_model, _cached_metadata

    @classmethod
    def get_scaler(cls) -> ChannelScaler:
        """
        Retrieves the fitted ChannelScaler instance.
        """
        global _cached_scaler
        with _lock:
            if _cached_scaler is not None:
                return _cached_scaler

            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            scaler_path = os.path.join(root_dir, "data", "processed", "scaler.pkl")

            if os.path.exists(scaler_path):
                try:
                    with open(scaler_path, "rb") as f:
                        scaler = pickle.load(f)
                    if isinstance(scaler, ChannelScaler):
                        _cached_scaler = scaler
                        logger.info("Loaded fitted ChannelScaler from %s", scaler_path)
                        return _cached_scaler
                except Exception as e:
                    logger.warning("Error unpickling scaler from %s: %s", scaler_path, e)

            # Fallback: create fresh ChannelScaler with verified physical constants
            logger.info("Instantiating standard physical ChannelScaler.")
            scaler = ChannelScaler(
                dbz_max=75.0,
                vil_max=65.0,
                tir_ground_c=35.0,
                tir_range_c=120.0,
                flash_max=25.0,
            )
            _cached_scaler = scaler
            return _cached_scaler

"""
Production Model Manager & Async Inference Engine.
Phase 8 Operational Platform — Unified Singleton, Thread-Safe, Zero-Overhead Inference.
"""
import os
import time
import asyncio
import threading
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
import numpy as np

import tensorflow as tf
from ml.model_registry import ModelRegistry
from dataset_pipeline.scaler import ChannelScaler
from reliability.warmup import ModelWarmupEngine
from reliability.numerical import NumericalSafetyValidator

# Global lock for thread-safe model swapping
_SWAP_LOCK = threading.RLock()

def weighted_convective_loss(y_true, y_pred):
    """Balanced Mean Absolute Error loss function emphasizing convective storm cores."""
    error = tf.abs(y_true - y_pred)
    weight = 1.0 + 4.0 * tf.cast(y_true >= 0.25, tf.float32) + 8.0 * tf.cast(y_true >= 0.40, tf.float32)
    return tf.reduce_mean(weight * error)

class ModelManager:
    """
    Unified singleton managing loaded model weights, warmup, hardware detection,
    and non-blocking async inference.
    """
    _instance: Optional["ModelManager"] = None
    _init_lock = threading.Lock()

    def __init__(self):
        self.registry = ModelRegistry()
        self.model: Optional[tf.keras.Model] = None
        self.model_id: str = "none"
        self.model_version: str = "none"
        self.model_hash: str = "none"
        self.model_mode: str = "real"
        self.scaler: Optional[ChannelScaler] = None
        self.status: str = "uninitialized"  # uninitialized, loading, ready, failed
        self.hardware: str = "cpu"
        self.device_name: str = "CPU"
        self.last_warmup_latency_ms: float = 0.0
        self.total_inferences: int = 0
        self.total_inference_time_ms: float = 0.0

        self._detect_hardware()
        self.load_active_production_model()

    def is_ready(self) -> bool:
        return self.status == "ready" and self.model is not None

    @classmethod
    def get_instance(cls) -> "ModelManager":
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _detect_hardware(self):
        """Detects GPU availability or falls back to optimized CPU vector instructions."""
        gpus = tf.config.list_physical_devices("GPU")
        if gpus:
            self.hardware = "gpu"
            self.device_name = gpus[0].name
            try:
                # Enable memory growth to prevent TensorFlow from seizing 100% VRAM
                for gpu in gpus:
                    tf.config.experimental.set_memory_growth(gpu, True)
            except Exception:
                pass
        else:
            self.hardware = "cpu"
            self.device_name = "CPU (AVX2/FMA vector acceleration)"

    def load_active_production_model(self, force_mode: Optional[str] = None):
        """Loads the active production model once into memory."""
        with _SWAP_LOCK:
            self.status = "loading"
            try:
                # 1. Load Scaler
                scaler_path = Path(__file__).parent.parent.parent / "data" / "processed" / "scaler.pkl"
                if scaler_path.exists():
                    self.scaler = ChannelScaler.load(str(scaler_path))
                else:
                    self.scaler = ChannelScaler()

                # 2. Query registry for active production model
                prod_meta = self.registry.get_production_model()
                weights_path = None
                if prod_meta and Path(prod_meta["weights_path"]).exists():
                    # Phase 10: Enforce artifact integrity before loading
                    is_valid, reg_hash, actual_hash = self.registry.verify_artifact_integrity(prod_meta["model_id"])
                    if not is_valid:
                        self.status = "failed"
                        raise RuntimeError(
                            f"OPERATIONAL INTEGRITY FAILURE: Model artifact {prod_meta['model_id']} "
                            f"integrity verification failed! Expected: {reg_hash}, Actual: {actual_hash}."
                        )
                    weights_path = prod_meta["weights_path"]
                    self.model_id = prod_meta["model_id"]
                    self.model_version = prod_meta["version"]
                    self.model_hash = prod_meta["model_hash"]
                else:
                    # Fallback to local files
                    fallback_real = Path(__file__).parent.parent / "models" / "convlstm_real_best.keras"
                    fallback_sim = Path(__file__).parent.parent / "models" / "convlstm_nowcaster.keras"
                    if fallback_real.exists():
                        weights_path = str(fallback_real)
                        self.model_id = "convlstm_real_best"
                        self.model_version = "1.0.0"
                    elif fallback_sim.exists():
                        weights_path = str(fallback_sim)
                        self.model_id = "convlstm_nowcaster"
                        self.model_version = "0.9.0"

                if weights_path and Path(weights_path).exists():
                    self.model = tf.keras.models.load_model(
                        weights_path,
                        custom_objects={"weighted_convective_loss": weighted_convective_loss},
                        compile=False,
                    )
                    self.model_mode = "real" if "real" in self.model_id else "simulation"
                    self._warmup()
                    self.status = "ready"
                else:
                    self.status = "failed"
            except Exception as e:
                self.status = "failed"
                raise RuntimeError(f"Failed to load production nowcasting model: {e}")

    def _warmup(self):
        """Executes synthetic benchmark warmup to compile TensorFlow graph and verify numerical validity."""
        if self.model is None:
            return
        result = ModelWarmupEngine.execute_warmup(self.model)
        self.last_warmup_latency_ms = result.latency_ms
        if not result.success:
            self.status = "failed"
            raise RuntimeError(f"Warmup verification failed: {result.error}")

    def predict_sync(self, tensor_4d: np.ndarray, forecast_steps: int = 4) -> np.ndarray:
        """
        Synchronous forward pass and autoregressive rollout.
        Thread-safe under _SWAP_LOCK.
        """
        with _SWAP_LOCK:
            if self.model is None or self.status != "ready":
                raise RuntimeError("Cannot infer: ModelManager is not ready")

            start = time.perf_counter()

            # Ensure batch dimension
            if tensor_4d.ndim == 4:
                batch_in = np.expand_dims(tensor_4d, axis=0)
            else:
                batch_in = tensor_4d

            # Step 1: Model inference for first 4 steps (+15, +30, +45, +60 min)
            pred_1_4 = self.model.predict(batch_in, verbose=0)  # Shape: (1, 4, 32, 32, 4)

            if forecast_steps <= 4:
                result = pred_1_4[:, :forecast_steps, :, :, :]
            else:
                # Autoregressive rollout for steps 5 and 6 (+90, +120 min)
                rollout_in = pred_1_4
                pred_5_8 = self.model.predict(rollout_in, verbose=0)
                remaining = forecast_steps - 4
                result = np.concatenate([pred_1_4, pred_5_8[:, :remaining, :, :, :]], axis=1)

            elapsed_ms = (time.perf_counter() - start) * 1000.0
            self.total_inferences += 1
            self.total_inference_time_ms += elapsed_ms

            output_seq = result[0]  # Return (T, 32, 32, 4)
            # Phase 11: Validate numerical integrity of generated nowcast tensor
            NumericalSafetyValidator.validate_tensor(output_seq, "inference_output_tensor")

            return output_seq

    async def predict_async(self, tensor_4d: np.ndarray, forecast_steps: int = 4) -> np.ndarray:
        """
        Non-blocking async forward pass. Runs the CPU/GPU-bound TensorFlow prediction
        in a background worker thread, ensuring the FastAPI event loop is never blocked.
        """
        return await asyncio.to_thread(self.predict_sync, tensor_4d, forecast_steps)

    def get_telemetry(self) -> Dict[str, Any]:
        """Returns runtime performance telemetry for monitoring."""
        avg_latency = (
            self.total_inference_time_ms / self.total_inferences
            if self.total_inferences > 0
            else 0.0
        )
        return {
            "status": self.status,
            "model_id": self.model_id,
            "version": self.model_version,
            "mode": self.model_mode,
            "hardware": self.hardware,
            "device_name": self.device_name,
            "warmup_latency_ms": round(self.last_warmup_latency_ms, 2),
            "total_inferences": self.total_inferences,
            "average_latency_ms": round(avg_latency, 2),
        }

def get_model_manager() -> ModelManager:
    return ModelManager.get_instance()

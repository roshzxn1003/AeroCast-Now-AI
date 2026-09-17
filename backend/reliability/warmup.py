"""
Model Artifact Warmup & Numerical Validation on Boot for AeroCast-Now AI.
Phase 11 Platform Hardening — Reliability & Model Integrity.

Executes a deterministic synthetic benchmark tensor through the production model
on application startup or weights hot-reload to ensure tensor pipelines, GPU/CPU kernels,
and activation functions are physically and numerically valid before serving live traffic.
"""
from __future__ import annotations

import time
import numpy as np
from dataclasses import dataclass
from typing import Tuple, Optional, List

from .taxonomy import NumericalValidationError, ModelNotReadyError
from .logging import get_logger

logger = get_logger("aerocast.warmup")


@dataclass
class WarmupResult:
    success: bool
    latency_ms: float
    output_shape: Optional[Tuple[int, ...]] = None
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    has_nans: bool = False
    has_infs: bool = False
    error: Optional[str] = None


class ModelWarmupEngine:
    """Executes safe synthetic warmup fixture on neural network models."""

    @staticmethod
    def generate_synthetic_benchmark_fixture(batch_size: int = 1) -> np.ndarray:
        """Generates normalized (batch, 4, 32, 32, 4) tensor within valid meteorological bounds."""
        # 4 channels: [Radar Reflectivity, VIL, Satellite TIR, Lightning Density]
        rng = np.random.RandomState(42)  # Deterministic seed
        tensor = rng.uniform(0.0, 1.0, size=(batch_size, 4, 32, 32, 4)).astype(np.float32)
        return tensor

    @classmethod
    def execute_warmup(cls, model) -> WarmupResult:
        """
        Runs synthetic benchmark fixture through model.
        Verifies execution latency, output tensor dimensions, and absence of NaNs/Infs.
        """
        if model is None:
            return WarmupResult(success=False, latency_ms=0.0, error="Model object is None")

        fixture = cls.generate_synthetic_benchmark_fixture()
        t0 = time.time()
        try:
            # Model prediction invocation
            pred = model.predict(fixture, verbose=0)
            latency_ms = round((time.time() - t0) * 1000.0, 2)
            
            # Check numerical validity
            pred_arr = np.asarray(pred)
            has_nans = bool(np.isnan(pred_arr).any())
            has_infs = bool(np.isinf(pred_arr).any())

            if has_nans or has_infs:
                err = f"Warmup generated non-finite values (NaN: {has_nans}, Inf: {has_infs})"
                logger.error(err)
                return WarmupResult(
                    success=False,
                    latency_ms=latency_ms,
                    output_shape=pred_arr.shape,
                    has_nans=has_nans,
                    has_infs=has_infs,
                    error=err,
                )

            logger.info(
                f"Model warmup successful in {latency_ms}ms, output shape {pred_arr.shape}",
                extra={"event": "model_warmup_completed", "duration_ms": latency_ms, "status": "success"},
            )

            return WarmupResult(
                success=True,
                latency_ms=latency_ms,
                output_shape=pred_arr.shape,
                min_val=float(np.min(pred_arr)),
                max_val=float(np.max(pred_arr)),
                has_nans=False,
                has_infs=False,
            )

        except Exception as e:
            latency_ms = round((time.time() - t0) * 1000.0, 2)
            err_msg = f"Model warmup failed: {str(e)}"
            logger.error(err_msg, exc_info=True)
            return WarmupResult(
                success=False,
                latency_ms=latency_ms,
                error=err_msg,
            )

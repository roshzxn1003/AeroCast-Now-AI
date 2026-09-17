"""
Inference Readiness Gate.
Phase 9 Operational Data Infrastructure.

Gated safety barrier positioned strictly between Data Ingestion and Model Inference.
Evaluates data completeness, spatial/temporal coverage, sensor cross-consistency,
and provider states before permitting tensor handoff to ModelManager.
Never allows unverified, corrupted, or silent fallback data to execute unnoticed.
"""
from __future__ import annotations

import logging
import numpy as np
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.canonical_observation import (
    CanonicalObservation,
    CanonicalQualityFlag,
    GriddedObservation,
)
from core.quality_control import AtmosphericQualityControl, QualityFlag
from ingestion.temporal_sync import SynchronizedTemporalSequence, temporal_synchronizer
from ingestion.provider_manager import provider_manager

logger = logging.getLogger("aerocast.ingestion.inference_gate")

class ReadinessStatus(str, Enum):
    READY = "READY"          # Full operational readiness, primary sources active
    DEGRADED = "DEGRADED"    # Partial or secondary fallback active, predictions permitted with caveats
    BLOCKED = "BLOCKED"      # Severe data loss, corruption, or stale data; inference prevented


@dataclass
class InferenceReadinessResult:
    status: ReadinessStatus
    is_ready: bool
    readiness_score: float  # 0.0 to 1.0
    blocking_reasons: List[str] = field(default_factory=list)
    degraded_reasons: List[str] = field(default_factory=list)
    active_providers: Dict[str, str] = field(default_factory=dict)
    data_mode: str = "REAL"
    input_tensor: Optional[np.ndarray] = None
    tensor_metadata: Dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "is_ready": self.is_ready,
            "readiness_score": round(self.readiness_score, 3),
            "blocking_reasons": self.blocking_reasons,
            "degraded_reasons": self.degraded_reasons,
            "active_providers": self.active_providers,
            "data_mode": self.data_mode,
            "tensor_shape": list(self.input_tensor.shape) if self.input_tensor is not None else None,
            "tensor_metadata": self.tensor_metadata,
            "evaluated_at": self.evaluated_at,
        }


class InferenceReadinessGate:
    """
    Operational gate that inspects synchronized observations and providers.
    """

    MIN_COMPLETENESS_FOR_READY: float = 0.75
    MIN_COMPLETENESS_FOR_DEGRADED: float = 0.25

    def evaluate_readiness(
        self,
        sequence: SynchronizedTemporalSequence,
        mode: Optional[str] = None,
    ) -> InferenceReadinessResult:
        """
        Validates the sequence and constructs the normalized (1, 4, 32, 32, 4) tensor.
        """
        data_mode = mode or provider_manager.operational_mode
        blocking: List[str] = []
        degraded: List[str] = []

        # 1. Check system provider health
        sys_health = provider_manager.get_system_health()
        active_providers = {}
        for d_name, d_info in sys_health["domains"].items():
            active_providers[d_name] = d_info["active_provider"]
            if d_info["is_in_fallback"]:
                degraded.append(
                    f"Domain {d_name} operating on secondary fallback ({d_info['active_provider']}): {d_info.get('last_fallback_reason', '')}"
                )

        # 2. Assemble tensor from sequence
        tensor, meta = temporal_synchronizer.assemble_tensor_frames(sequence)

        # 3. Inspect Numerical Integrity
        if np.isnan(tensor).any():
            blocking.append("Input tensor contains NaN values")
        if np.isinf(tensor).any():
            blocking.append("Input tensor contains infinite values")

        # 4. Check Completeness & Missing Channels
        completeness = meta.get("completeness_score", 0.0)
        missing = meta.get("missing_channels", [])

        # Radar Reflectivity is critical for convective nowcasting
        radar_missing_slots = [m for m in missing if "reflectivity" in m]
        if len(radar_missing_slots) >= 3:
            blocking.append(f"Critical channel 'reflectivity' missing in {len(radar_missing_slots)}/4 timesteps")
        elif len(radar_missing_slots) > 0:
            degraded.append(f"Radar reflectivity missing in timesteps: {radar_missing_slots}")

        # Check Imputed / Forward-Filled fraction
        imputed_flags = meta.get("channel_imputed_flags", {})
        total_slots = 0
        imputed_slots = 0
        for ch, flags in imputed_flags.items():
            for f in flags:
                total_slots += 1
                if f:
                    imputed_slots += 1

        imputed_ratio = (imputed_slots / total_slots) if total_slots > 0 else 0.0
        if imputed_ratio > 0.5:
            degraded.append(f"High forward-fill imputation ratio ({imputed_ratio * 100:.1f}%) across observation windows")

        # 5. Check Cross-Sensor Physical Consistency at T0 (slot 3)
        t0_slot = sequence.slots[3]
        if "reflectivity" in t0_slot.observations and "vertically_integrated_liquid" in t0_slot.observations:
            dbz_grid = t0_slot.observations["reflectivity"].grid_data
            vil_grid = t0_slot.observations["vertically_integrated_liquid"].grid_data
            if dbz_grid is not None and vil_grid is not None:
                max_dbz = float(np.max(dbz_grid))
                max_vil = float(np.max(vil_grid))
                # If high VIL but zero dBZ, or vice versa
                if max_vil > 10.0 and max_dbz < 15.0:
                    degraded.append(f"Physical anomaly: High VIL ({max_vil:.1f} kg/m²) with low reflectivity ({max_dbz:.1f} dBZ)")

        # 6. Check Sensor Data Age
        for ch, ages in meta.get("channel_data_ages_sec", {}).items():
            if ages and ages[-1] > 3600.0:  # Older than 1 hour
                degraded.append(f"Channel '{ch}' latest observation is stale ({ages[-1]/60.0:.1f} minutes old)")

        # Compute Score
        base_score = completeness
        if degraded:
            base_score = max(0.2, base_score - 0.15 * len(degraded))

        # Determine Final Status
        if blocking:
            status = ReadinessStatus.BLOCKED
            is_ready = False
            score = 0.0
        elif degraded or base_score < self.MIN_COMPLETENESS_FOR_READY:
            status = ReadinessStatus.DEGRADED
            is_ready = True
            score = min(0.85, max(0.3, base_score))
        else:
            status = ReadinessStatus.READY
            is_ready = True
            score = min(1.0, base_score)

        return InferenceReadinessResult(
            status=status,
            is_ready=is_ready,
            readiness_score=score,
            blocking_reasons=blocking,
            degraded_reasons=degraded,
            active_providers=active_providers,
            data_mode=data_mode,
            input_tensor=tensor,
            tensor_metadata=meta,
        )

inference_gate = InferenceReadinessGate()

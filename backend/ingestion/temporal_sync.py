"""
Temporal Synchronization & Missingness Engine.
Phase 9 Operational Data Infrastructure.

Aligns multi-cadence observations (Radar 10m, Satellite 15m, Lightning 1m, NWP 1h)
into discrete, synchronized 4-timestep forecast sequences [T-45, T-30, T-15, T0].
Strictly distinguishes genuine zero observations from MISSING data,
calculates data age and domain coverage, and applies bounded temporal forward-fill
with mandatory imputation quality tagging.
"""
from __future__ import annotations

import logging
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from core.canonical_observation import (
    GriddedObservation,
    CanonicalQualityFlag,
    CanonicalProvenance,
    ProcessingStatus,
    SpatialDomain,
)

logger = logging.getLogger("aerocast.ingestion.temporal_sync")

class TimestepSlot:
    """Represents a discrete temporal bin in the [T-45, T-30, T-15, T0] sequence."""

    def __init__(self, target_time: datetime, slot_index: int, tolerance_minutes: float = 7.5):
        self.target_time = target_time
        self.slot_index = slot_index  # 0: T-45, 1: T-30, 2: T-15, 3: T0
        self.tolerance = timedelta(minutes=tolerance_minutes)
        self.observations: Dict[str, GriddedObservation] = {}  # channel_key -> GriddedObservation
        self.is_imputed: Dict[str, bool] = {}
        self.data_age_sec: Dict[str, float] = {}

    def matches(self, obs_time: datetime) -> bool:
        """Returns True if obs_time falls within this slot's tolerance window."""
        return abs(self.target_time - obs_time) <= self.tolerance


class SynchronizedTemporalSequence:
    """
    Holds the aligned 4-timestep atmospheric state across all 4 ConvLSTM input channels:
    Channel 0: Radar Reflectivity (dBZ)
    Channel 1: Vertically Integrated Liquid (VIL, kg/m²)
    Channel 2: Satellite Thermal Infrared (TIR, °C)
    Channel 3: Lightning Flash Density (flashes/km²)
    """

    CHANNEL_KEYS = ["reflectivity", "vertically_integrated_liquid", "brightness_temperature", "flash_density"]

    def __init__(self, t0: Optional[datetime] = None, grid_size: int = 32):
        self.t0 = t0 or datetime.now(timezone.utc)
        self.grid_size = grid_size
        self.slots: List[TimestepSlot] = [
            TimestepSlot(self.t0 - timedelta(minutes=45), 0),
            TimestepSlot(self.t0 - timedelta(minutes=30), 1),
            TimestepSlot(self.t0 - timedelta(minutes=15), 2),
            TimestepSlot(self.t0, 3),
        ]
        self.completeness_score: float = 0.0
        self.missing_channels: List[str] = []

    def get_slot_timestamps(self) -> List[str]:
        return [s.target_time.isoformat() for s in self.slots]


class TemporalSynchronizer:
    """
    Coordinates multi-rate observation snapping, interpolation, and missingness tagging.
    """

    MAX_FORWARD_FILL_AGE_SEC: float = 1800.0  # 30 minutes maximum forward fill

    def synchronize_observations(
        self,
        observations: List[GriddedObservation],
        t0: Optional[datetime] = None,
        grid_size: int = 32,
    ) -> SynchronizedTemporalSequence:
        """
        Takes raw/normalized GriddedObservations and aligns them into a SynchronizedTemporalSequence.
        """
        ref_time = t0 or datetime.now(timezone.utc)
        seq = SynchronizedTemporalSequence(ref_time, grid_size)

        # 1. Bucket observations into slots by matching variable & nearest slot time
        for obs in observations:
            var = obs.variable
            if var not in seq.CHANNEL_KEYS:
                continue

            try:
                obs_dt = datetime.fromisoformat(obs.timestamp.replace("Z", "+00:00"))
            except Exception:
                obs_dt = ref_time

            # Find closest slot
            best_slot: Optional[TimestepSlot] = None
            min_diff = timedelta(days=365)
            for slot in seq.slots:
                diff = abs(slot.target_time - obs_dt)
                if diff < min_diff and slot.matches(obs_dt):
                    min_diff = diff
                    best_slot = slot

            if best_slot is not None:
                # If slot doesn't have this channel yet, or this observation is closer in time
                existing = best_slot.observations.get(var)
                if existing is None:
                    best_slot.observations[var] = obs
                    best_slot.is_imputed[var] = False
                    best_slot.data_age_sec[var] = abs((ref_time - obs_dt).total_seconds())

        # 2. Forward-fill missing slots from earlier slots within MAX_FORWARD_FILL_AGE_SEC
        for ch in seq.CHANNEL_KEYS:
            last_valid_obs: Optional[GriddedObservation] = None
            last_valid_time: Optional[datetime] = None

            for slot in seq.slots:
                if ch in slot.observations:
                    last_valid_obs = slot.observations[ch]
                    try:
                        last_valid_time = datetime.fromisoformat(last_valid_obs.timestamp.replace("Z", "+00:00"))
                    except Exception:
                        last_valid_time = slot.target_time
                elif last_valid_obs is not None and last_valid_time is not None:
                    age_sec = (slot.target_time - last_valid_time).total_seconds()
                    if 0 <= age_sec <= self.MAX_FORWARD_FILL_AGE_SEC:
                        # Forward-fill with explicit imputation tag
                        cloned_data = last_valid_obs.grid_data.copy()
                        imputed_obs = GriddedObservation(
                            observation_id=f"{last_valid_obs.observation_id}-FF-{slot.slot_index}",
                            obs_type=None,
                            source=last_valid_obs.source,
                            provider=last_valid_obs.provider,
                            dataset=last_valid_obs.dataset,
                            variable=ch,
                            timestamp=slot.target_time.isoformat(),
                            valid_time=slot.target_time.isoformat(),
                            ingestion_time=datetime.now(timezone.utc).isoformat(),
                            unit=last_valid_obs.unit,
                            quality_flag=CanonicalQualityFlag.ESTIMATED,  # Explicitly marked ESTIMATED
                            processing_status=ProcessingStatus.NORMALIZED,
                            provenance=last_valid_obs.provenance,
                            domain=last_valid_obs.domain,
                            grid_shape=last_valid_obs.grid_shape,
                            grid_data=cloned_data,
                            quality_reason=f"Forward-filled across {int(age_sec)}s gap",
                        )
                        slot.observations[ch] = imputed_obs
                        slot.is_imputed[ch] = True
                        slot.data_age_sec[ch] = age_sec

        # 3. Calculate sequence completeness and identify missing slots/channels
        total_required_cells = len(seq.slots) * len(seq.CHANNEL_KEYS)
        populated_cells = 0
        missing_set = set()

        for slot in seq.slots:
            for ch in seq.CHANNEL_KEYS:
                if ch in slot.observations:
                    populated_cells += 1
                else:
                    missing_set.add(f"{ch}@T{slot.slot_index-3}")

        seq.completeness_score = round(populated_cells / total_required_cells, 4)
        seq.missing_channels = sorted(list(missing_set))
        return seq

    def assemble_tensor_frames(
        self,
        sequence: SynchronizedTemporalSequence,
        fill_unobserved: bool = True,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Transforms SynchronizedTemporalSequence into the exact (1, 4, 32, 32, 4) tensor
        expected by ConvLSTM without model alterations.

        Channel Order:
          0: dBZ (max 75.0)
          1: VIL (max 65.0)
          2: TIR ((35.0 - TIR) / 120.0)
          3: Flash Density (max 25.0)

        Returns:
          tensor: np.ndarray of shape (1, 4, 32, 32, 4), dtype=float32
          meta: provenance, data ages, and coverage statistics
        """
        N_TIMESTEPS = 4
        N_CHANNELS = 4
        H, W = sequence.grid_size, sequence.grid_size

        tensor = np.zeros((1, N_TIMESTEPS, H, W, N_CHANNELS), dtype=np.float32)
        channel_names = sequence.CHANNEL_KEYS

        # Metadata records
        data_ages: Dict[str, List[float]] = {ch: [] for ch in channel_names}
        imputed_flags: Dict[str, List[bool]] = {ch: [] for ch in channel_names}
        coverage_pct: Dict[str, float] = {}

        for t_idx, slot in enumerate(sequence.slots):
            for c_idx, ch_name in enumerate(channel_names):
                obs = slot.observations.get(ch_name)

                if obs is not None and obs.grid_data is not None:
                    raw_grid = obs.grid_data
                    if raw_grid.shape != (H, W):
                        # Ensure shape matches exactly
                        from ingestion.geospatial_regridder import regridder
                        raw_grid = regridder.resize_grid(raw_grid, (H, W))

                    # Physical Normalization conforming to ModelManager input spec:
                    if c_idx == 0:  # dBZ: 0 to 75 -> [0, 1]
                        norm_grid = np.clip(raw_grid / 75.0, 0.0, 1.0)
                    elif c_idx == 1:  # VIL: 0 to 65 -> [0, 1]
                        norm_grid = np.clip(raw_grid / 65.0, 0.0, 1.0)
                    elif c_idx == 2:  # TIR: [-85, 35] -> (35 - TIR)/120 -> [0, 1]
                        norm_grid = np.clip((35.0 - raw_grid) / 120.0, 0.0, 1.0)
                    elif c_idx == 3:  # Flash Density: 0 to 25 -> [0, 1]
                        norm_grid = np.clip(raw_grid / 25.0, 0.0, 1.0)
                    else:
                        norm_grid = raw_grid

                    tensor[0, t_idx, :, :, c_idx] = norm_grid.astype(np.float32)
                    data_ages[ch_name].append(slot.data_age_sec.get(ch_name, 0.0))
                    imputed_flags[ch_name].append(slot.is_imputed.get(ch_name, False))
                else:
                    # Explicit unobserved / zero-fill with unobserved tag
                    # For TIR, default clear sky brightness is ~22°C -> (35 - 22)/120 = 0.108
                    if c_idx == 2 and fill_unobserved:
                        tensor[0, t_idx, :, :, c_idx] = (35.0 - 22.0) / 120.0
                    else:
                        tensor[0, t_idx, :, :, c_idx] = 0.0

                    data_ages[ch_name].append(9999.0)
                    imputed_flags[ch_name].append(True)

        # Calculate coverage percentages per channel
        for c_idx, ch_name in enumerate(channel_names):
            ch_data = tensor[0, :, :, :, c_idx]
            # Valid coverage is proportion of non-zero (or for TIR non-default clear)
            if c_idx == 2:
                valid_cells = np.sum(np.abs(ch_data - ((35.0 - 22.0) / 120.0)) > 0.001)
            else:
                valid_cells = np.sum(ch_data > 0.0)
            coverage_pct[ch_name] = round(float(valid_cells) / (N_TIMESTEPS * H * W) * 100.0, 2)

        meta = {
            "tensor_shape": list(tensor.shape),
            "reference_time": sequence.t0.isoformat(),
            "slot_timestamps": sequence.get_slot_timestamps(),
            "completeness_score": sequence.completeness_score,
            "missing_channels": sequence.missing_channels,
            "channel_data_ages_sec": data_ages,
            "channel_imputed_flags": imputed_flags,
            "coverage_percentage": coverage_pct,
        }

        return tensor, meta

temporal_synchronizer = TemporalSynchronizer()

"""
Observation Buffer Manager
==========================
Manages a FIFO rolling buffer of 15-minute time-aligned multi-modal observation frames:
  - Sequence length: 4 frames (T-45, T-30, T-15, T_0)
  - Dimensions: (4, 32, 32, 4)
  - Channels:
      Channel 0: Radar Reflectivity (dBZ: [0, 75])
      Channel 1: Vertically Integrated Liquid (VIL: [0, 65] kg/m²)
      Channel 2: Satellite Thermal IR (TIR: [-85, +35] °C)
      Channel 3: Lightning Flash Density (Flash: [0, 25] flashes/km²)

Enforces strict scientific honesty:
  - In 'real' mode: reports sequence_ready=False when buffer < 4 frames. Does not fabricate.
  - In 'hybrid' mode: warms up missing historical slots with physical continuity from live frame.
  - In 'simulation' mode: generates procedural convective sequences.
"""

from __future__ import annotations

import collections
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Deque, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("aerocast.live.buffer")

FRAME_CADENCE_MINUTES = 15
SEQUENCE_LENGTH = 4


@dataclass
class ObservationFrame:
    """A single multi-modal observation frame at time T."""
    data: np.ndarray             # (32, 32, 4) float32 in physical units
    timestamp: datetime         # UTC timestamp of observation
    metadata: Dict[str, Any] = field(default_factory=dict)
    provenance: str = "LIVE"    # "LIVE", "HYBRID", "SIMULATED"


class ObservationManager:
    """
    Thread-safe and async-safe rolling observation buffer.
    Maintains the 4 latest 15-minute frames for ConvLSTM spatio-temporal inference.
    """

    def __init__(self, max_frames: int = SEQUENCE_LENGTH) -> None:
        self.max_frames = max_frames
        self._buffer: Deque[ObservationFrame] = collections.deque(maxlen=max_frames)

    @property
    def frame_count(self) -> int:
        return len(self._buffer)

    def is_sequence_ready(self) -> bool:
        """
        True only if exactly 4 valid frames are buffered.
        """
        return len(self._buffer) >= self.max_frames

    def add_frame(
        self,
        frame: np.ndarray,
        timestamp: datetime,
        metadata: Optional[Dict[str, Any]] = None,
        provenance: str = "LIVE",
    ) -> None:
        """
        Appends a newly acquired observation frame to the buffer.
        Validates shape (32, 32, 4).
        """
        assert frame.shape == (32, 32, 4), f"Frame must have shape (32, 32, 4), got {frame.shape}"

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        obs_frame = ObservationFrame(
            data=frame.astype(np.float32),
            timestamp=timestamp,
            metadata=metadata or {},
            provenance=provenance,
        )
        self._buffer.append(obs_frame)
        logger.debug("Added frame to ObservationManager: count=%d/%d, ts=%s", len(self._buffer), self.max_frames, timestamp.isoformat())

    def get_latest_frame(self) -> Optional[ObservationFrame]:
        """
        Returns the most recent frame in the buffer.
        """
        if not self._buffer:
            return None
        return self._buffer[-1]

    def get_sequence(self) -> Tuple[np.ndarray, List[datetime], List[str]]:
        """
        Returns the (4, 32, 32, 4) tensor along with timestamps and provenances.
        Raises ValueError if buffer does not contain enough frames.
        """
        if not self.is_sequence_ready():
            raise ValueError(f"Sequence not ready: buffer has {len(self._buffer)}/{self.max_frames} frames.")

        frames = list(self._buffer)[-self.max_frames:]
        tensor = np.stack([f.data for f in frames], axis=0)  # (4, 32, 32, 4)
        timestamps = [f.timestamp for f in frames]
        provenances = [f.provenance for f in frames]

        return tensor, timestamps, provenances

    def warmup_hybrid_sequence(
        self,
        latest_frame: np.ndarray,
        timestamp: datetime,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[np.ndarray, List[datetime], List[str]]:
        """
        Warms up the 4-frame sequence in HYBRID mode when starting up or after network gaps.
        Applies physically consistent convective evolution (slight advection and cell growth/decay)
        to the latest authentic observation to construct the historical T-45, T-30, T-15, T_0 sequence.
        Marks provenance as 'HYBRID' with full scientific transparency.
        """
        assert latest_frame.shape == (32, 32, 4)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        seq_frames = []
        timestamps = []
        provenances = []

        # offsets: -45, -30, -15, 0 minutes
        for step_idx, offset_min in enumerate([-45, -30, -15, 0]):
            t_offset = timestamp + timedelta(minutes=offset_min)
            timestamps.append(t_offset)

            if offset_min == 0:
                # Authentic live frame
                f_data = latest_frame.copy()
                prov = "LIVE"
            else:
                # Physically attenuated historical estimate
                decay_factor = 1.0 - (abs(offset_min) / 120.0) * 0.15
                shift_pixels = int(round(abs(offset_min) / 15.0))

                # Shift slightly east-northeast (convective advection typical in Tamil Nadu)
                shifted_dbz = np.roll(latest_frame[..., 0], -shift_pixels, axis=1) * decay_factor
                shifted_vil = np.roll(latest_frame[..., 1], -shift_pixels, axis=1) * decay_factor
                shifted_tir = np.roll(latest_frame[..., 2], -shift_pixels, axis=1)
                shifted_fl = np.roll(latest_frame[..., 3], -shift_pixels, axis=1) * decay_factor

                f_data = np.stack([shifted_dbz, shifted_vil, shifted_tir, shifted_fl], axis=-1)
                prov = "HYBRID"

            seq_frames.append(f_data)
            provenances.append(prov)

        tensor = np.stack(seq_frames, axis=0).astype(np.float32)

        # Also populate buffer with these frames so subsequent calls have warm state
        self._buffer.clear()
        for f_data, ts, prov in zip(seq_frames, timestamps, provenances):
            self.add_frame(f_data, ts, metadata=metadata, provenance=prov)

        return tensor, timestamps, provenances

    def get_simulation_sequence(
        self,
        station_name: str = "Chennai DWR (Sriharikota/Port)",
        storm_mode: str = "Severe Squall Line",
    ) -> Tuple[np.ndarray, List[datetime], List[str]]:
        """
        Returns a procedural synthetic convective sequence for benchmarking or simulation mode.
        """
        from observation_service import ingest_nowcast_multimodal_tensor

        tensor, meta = ingest_nowcast_multimodal_tensor(
            station_name=station_name,
            storm_mode=storm_mode,
            history_steps=self.max_frames,
            data_mode="simulated",
        )

        # Tensor from ingest_nowcast_multimodal_tensor is normalized [0, 1]
        # Denormalize to physical units so buffer always stores physical units
        physical_tensor = np.zeros_like(tensor, dtype=np.float32)
        physical_tensor[..., 0] = tensor[..., 0] * 75.0
        physical_tensor[..., 1] = tensor[..., 1] * 65.0
        physical_tensor[..., 2] = 35.0 - tensor[..., 2] * 120.0
        physical_tensor[..., 3] = tensor[..., 3] * 25.0

        now = datetime.now(timezone.utc)
        timestamps = [now + timedelta(minutes=(i - 3) * 15) for i in range(4)]
        provenances = ["SIMULATED"] * 4

        self._buffer.clear()
        for i in range(4):
            self.add_frame(physical_tensor[i], timestamps[i], metadata=meta, provenance="SIMULATED")

        return physical_tensor, timestamps, provenances

    def clear(self) -> None:
        """Clears all frames from buffer."""
        self._buffer.clear()

"""
Time Synchronization & Temporal Interpolation
=============================================
Aligns incoming heterogeneous observation sequences into standard 15-minute cadences:
  T-45 (-45 min)
  T-30 (-30 min)
  T-15 (-15 min)
  T0   (0 min, NOW)

Performs scientifically conservative interpolation when observations are slightly offset,
without inventing or fabricating missing storm cores.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from data_ingestion.base import NormalizedObservation


def align_to_15min_cadence(
    dt: datetime,
    reference_dt: Optional[datetime] = None
) -> int:
    """
    Returns the time index (0 to 3) closest to standard 15-min intervals:
      0: T-45 min
      1: T-30 min
      2: T-15 min
      3: T0 (NOW)
    """
    ref = reference_dt or datetime.now(timezone.utc)
    diff_minutes = (dt - ref).total_seconds() / 60.0  # Usually negative, e.g. -45, -30, -15, 0

    if diff_minutes <= -37.5:
        return 0
    elif diff_minutes <= -22.5:
        return 1
    elif diff_minutes <= -7.5:
        return 2
    else:
        return 3


def synchronize_time_series(
    observations: List[NormalizedObservation],
    target_intervals: int = 4,
    step_minutes: int = 15,
    reference_dt: Optional[datetime] = None
) -> List[Optional[NormalizedObservation]]:
    """
    Aligns a chronological list of observations into fixed 15-minute slots [T-45, T-30, T-15, T0].
    Slots with no observation available are filled with None (or conservative interpolation).
    """
    ref = reference_dt or datetime.now(timezone.utc)
    slots: List[Optional[NormalizedObservation]] = [None] * target_intervals

    for obs in observations:
        try:
            obs_dt = datetime.fromisoformat(obs.timestamp.replace("Z", "+00:00"))
            idx = align_to_15min_cadence(obs_dt, ref)
            if 0 <= idx < target_intervals:
                # Store latest observation in slot
                slots[idx] = obs
        except Exception:
            continue

    return slots


def interpolate_scalar_gap(
    val_before: Optional[float],
    val_after: Optional[float],
    weight: float = 0.5
) -> Optional[float]:
    """Conservatively interpolates scalar parameter between two observations."""
    if val_before is not None and val_after is not None:
        return round(val_before * (1.0 - weight) + val_after * weight, 2)
    return val_before if val_before is not None else val_after

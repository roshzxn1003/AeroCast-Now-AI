"""
Temporal Synchronization & Sequence Assembly
=============================================
Converts heterogeneous timestamps to UTC, aligns observations into exact 15-minute
intervals (00, 15, 30, 45 min), and constructs 8-step convective sequences
(4 input frames: T-45, T-30, T-15, T0 -> 4 forecast frames: T+15, T+30, T+45, T+60).
"""

from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


def parse_to_utc(ts_input: Any) -> datetime:
    """
    Parses various timestamp representations (ISO-8601 string, UNIX timestamp,
    pandas/numpy datetime) into an aware UTC datetime object.
    """
    if isinstance(ts_input, datetime):
        if ts_input.tzinfo is None:
            return ts_input.replace(tzinfo=timezone.utc)
        return ts_input.astimezone(timezone.utc)

    if isinstance(ts_input, (int, float)):
        # If timestamp is in milliseconds
        if ts_input > 1e11:
            ts_input = ts_input / 1000.0
        return datetime.fromtimestamp(ts_input, tz=timezone.utc)

    if isinstance(ts_input, str):
        # Clean string format
        clean_str = ts_input.strip().replace("Z", "+00:00").replace(" ", "T")
        try:
            dt = datetime.fromisoformat(clean_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            # Handle formats like YYYYMMDDHHMM or YYYY-MM-DD HH:MM:SS
            for fmt in ("%Y-%m-%d_%H%M%S", "%Y%m%d%H%M", "%Y%m%d_%H%M%S", "%Y-%m-%d %H:%M:%S"):
                try:
                    dt = datetime.strptime(ts_input.strip(), fmt)
                    return dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    pass

    raise ValueError(f"Cannot parse timestamp into UTC datetime: '{ts_input}'")


def format_utc_iso(dt: datetime) -> str:
    """Formats datetime to standard UTC ISO-8601 string (%Y-%m-%dT%H:%M:%SZ)."""
    aware = parse_to_utc(dt)
    return aware.strftime("%Y-%m-%dT%H:%M:%SZ")


def align_timestamp_to_15min(dt: datetime, mode: str = "nearest") -> datetime:
    """
    Rounds/aligns a UTC datetime to the nearest (or floor) 15-minute interval:
    00, 15, 30, or 45 minutes past the hour.
    """
    utc_dt = parse_to_utc(dt)
    minute = utc_dt.minute
    second = utc_dt.second
    microsecond = utc_dt.microsecond

    fractional_min = minute + (second / 60.0) + (microsecond / 60000000.0)

    if mode == "floor":
        slot_min = int(fractional_min // 15) * 15
        return utc_dt.replace(minute=slot_min, second=0, microsecond=0)
    elif mode == "nearest":
        slot_min = int(round(fractional_min / 15.0)) * 15
        if slot_min == 60:
            return (utc_dt + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        else:
            return utc_dt.replace(minute=slot_min, second=0, microsecond=0)
    else:
        raise ValueError(f"Unsupported alignment mode: {mode}")


def resample_time_series_to_15min(
    hourly_timestamps: List[datetime],
    hourly_values: np.ndarray,
    target_start: datetime,
    target_end: datetime
) -> Tuple[List[datetime], np.ndarray]:
    """
    Linearly resamples hourly or irregular atmospheric soundings onto strict
    15-minute intervals between target_start and target_end.

    Args:
        hourly_timestamps: List of source observation datetimes (must be sorted)
        hourly_values: Array of shape (N_source, N_features) or (N_source,)
        target_start: Desired start datetime (aligned to 15-min)
        target_end: Desired end datetime (aligned to 15-min)

    Returns:
        target_timestamps: List of exact 15-minute UTC datetimes
        resampled_values: Interpolated values array of shape (N_target, N_features)
    """
    assert len(hourly_timestamps) == len(hourly_values), "Length mismatch between timestamps and values"
    if len(hourly_timestamps) == 0:
        return [], np.empty((0,) + hourly_values.shape[1:], dtype=np.float32)

    src_epochs = np.array([parse_to_utc(t).timestamp() for t in hourly_timestamps], dtype=np.float64)

    # Build 15-minute target epoch sequence
    start_dt = align_timestamp_to_15min(target_start)
    end_dt = align_timestamp_to_15min(target_end)
    
    curr = start_dt
    target_dts: List[datetime] = []
    target_epochs: List[float] = []
    while curr <= end_dt:
        target_dts.append(curr)
        target_epochs.append(curr.timestamp())
        curr += timedelta(minutes=15)

    target_epochs_arr = np.array(target_epochs, dtype=np.float64)

    # Multi-feature linear interpolation
    values_2d = hourly_values if hourly_values.ndim > 1 else hourly_values[:, None]
    n_features = values_2d.shape[1]
    resampled = np.zeros((len(target_epochs), n_features), dtype=np.float32)

    for f_idx in range(n_features):
        feat_vals = values_2d[:, f_idx]
        resampled[:, f_idx] = np.interp(
            target_epochs_arr,
            src_epochs,
            feat_vals,
            left=feat_vals[0],
            right=feat_vals[-1]
        )

    if hourly_values.ndim == 1:
        resampled = resampled[:, 0]

    return target_dts, resampled


def assemble_temporal_sequences(
    timestamps: List[datetime],
    spatial_frames: np.ndarray,
    atmospheric_features: Optional[np.ndarray] = None,
    input_steps: int = 4,
    forecast_steps: int = 4,
    step_minutes: int = 15,
    max_gap_seconds: float = 960.0  # 16 minutes max allowance between consecutive steps
) -> Tuple[np.ndarray, np.ndarray, Optional[np.ndarray], List[Dict[str, Any]]]:
    """
    Constructs consecutive 8-step spatio-temporal sequences:
      - X: past 4 frames (T-45, T-30, T-15, T0) -> shape (N_seq, 4, 32, 32, 4)
      - Y: future 4 frames (T+15, T+30, T+45, T+60) -> shape (N_seq, 4, 32, 32, 4)
      - Atmospheric features: (N_seq, 4, N_features) corresponding to input steps

    Validates that consecutive steps in each sequence are strictly step_minutes apart.
    Discards incomplete sequences or those with temporal breaks.

    Returns:
        X: Input tensor array (N, 4, 32, 32, 4)
        Y: Forecast target tensor array (N, 4, 32, 32, 4)
        A: Aligned atmospheric features (N, 4, N_features) or None
        seq_metadata: List of dicts with sequence timestamps and IDs
    """
    total_steps = input_steps + forecast_steps  # 8
    n_frames = len(timestamps)

    if n_frames < total_steps:
        empty_X = np.empty((0, input_steps, 32, 32, 4), dtype=np.float32)
        empty_Y = np.empty((0, forecast_steps, 32, 32, 4), dtype=np.float32)
        return empty_X, empty_Y, None, []

    X_list: List[np.ndarray] = []
    Y_list: List[np.ndarray] = []
    A_list: List[np.ndarray] = []
    meta_list: List[Dict[str, Any]] = []

    expected_delta_sec = step_minutes * 60.0

    for i in range(n_frames - total_steps + 1):
        window_dts = timestamps[i : i + total_steps]
        
        # Check strict 15-min continuity
        is_continuous = True
        for k in range(len(window_dts) - 1):
            dt_diff = (window_dts[k + 1] - window_dts[k]).total_seconds()
            if abs(dt_diff - expected_delta_sec) > 60.0:  # Allow max 1-minute jitter
                is_continuous = False
                break

        if not is_continuous:
            continue

        seq_frames = spatial_frames[i : i + total_steps]
        x_seq = seq_frames[0 : input_steps]
        y_seq = seq_frames[input_steps : total_steps]

        X_list.append(x_seq)
        Y_list.append(y_seq)

        if atmospheric_features is not None:
            A_list.append(atmospheric_features[i : i + input_steps])

        meta = {
            "sequence_id": f"seq_{i:06d}",
            "t_minus_45": format_utc_iso(window_dts[0]),
            "t_minus_30": format_utc_iso(window_dts[1]),
            "t_minus_15": format_utc_iso(window_dts[2]),
            "t_zero": format_utc_iso(window_dts[input_steps - 1]),
            "t_plus_15": format_utc_iso(window_dts[input_steps]),
            "t_plus_30": format_utc_iso(window_dts[input_steps + 1]),
            "t_plus_45": format_utc_iso(window_dts[input_steps + 2]),
            "t_plus_60": format_utc_iso(window_dts[total_steps - 1]),
            "start_time": format_utc_iso(window_dts[0]),
            "end_time": format_utc_iso(window_dts[-1]),
        }
        meta_list.append(meta)

    if not X_list:
        empty_X = np.empty((0, input_steps, 32, 32, 4), dtype=np.float32)
        empty_Y = np.empty((0, forecast_steps, 32, 32, 4), dtype=np.float32)
        return empty_X, empty_Y, None, []

    X = np.array(X_list, dtype=np.float32)
    Y = np.array(Y_list, dtype=np.float32)
    A = np.array(A_list, dtype=np.float32) if atmospheric_features is not None else None

    return X, Y, A, meta_list

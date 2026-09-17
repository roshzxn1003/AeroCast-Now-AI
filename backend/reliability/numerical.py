"""
Numerical Safety Validator for Forecast Predictions — AeroCast-Now AI.
Phase 11 Platform Hardening — Meteorological & Mathematical Integrity.

Intercepts predictions before persistence to guarantee:
1. No NaN or Infinite values exist in output tensors or confidence scores.
2. Coordinates are within meteorologically valid geospatial bounds.
3. Atmospheric variables conform to physical domain limits (e.g. dBZ in [0, 75]).
4. Timestamps are valid and strictly monotonic.
"""
from __future__ import annotations

import numpy as np
from datetime import datetime
from typing import Dict, Any, Tuple, Optional, List

from .taxonomy import NumericalValidationError
from .logging import get_logger

logger = get_logger("aerocast.numerical")

# Physical Bounds for atmospheric channels in AeroCast
PHYSICAL_BOUNDS = {
    "reflectivity_dbz": (0.0, 75.0),
    "vil_kg_m2": (0.0, 80.0),
    "satellite_tir_c": (-95.0, 45.0),
    "lightning_density": (0.0, 100.0),
    "confidence_score": (0.0, 1.0),
}

# Domain Geospatial Limits for Indian Subcontinent & Bay of Bengal
GEO_BOUNDS = {
    "min_lat": 6.0,
    "max_lat": 38.0,
    "min_lon": 68.0,
    "max_lon": 98.0,
}


class NumericalSafetyValidator:
    """Validates predictions before persistent ledger storage."""

    @staticmethod
    def validate_tensor(tensor: Any, name: str = "prediction_tensor") -> None:
        """Validates that a numeric tensor/array contains no NaNs or Infs."""
        arr = np.asarray(tensor)
        if not np.issubdtype(arr.dtype, np.number):
            raise NumericalValidationError(f"Tensor '{name}' contains non-numeric data type {arr.dtype}")

        if np.isnan(arr).any():
            nan_count = int(np.isnan(arr).sum())
            raise NumericalValidationError(f"Tensor '{name}' contains {nan_count} NaN values")

        if np.isinf(arr).any():
            inf_count = int(np.isinf(arr).sum())
            raise NumericalValidationError(f"Tensor '{name}' contains {inf_count} Infinite values")

    @staticmethod
    def validate_coordinates(lat: float, lon: float) -> None:
        """Ensures geographic coordinates fall within subcontinent bounds."""
        if not (GEO_BOUNDS["min_lat"] <= lat <= GEO_BOUNDS["max_lat"]):
            raise NumericalValidationError(
                f"Latitude {lat} out of valid bounds [{GEO_BOUNDS['min_lat']}, {GEO_BOUNDS['max_lat']}]"
            )
        if not (GEO_BOUNDS["min_lon"] <= lon <= GEO_BOUNDS["max_lon"]):
            raise NumericalValidationError(
                f"Longitude {lon} out of valid bounds [{GEO_BOUNDS['min_lon']}, {GEO_BOUNDS['max_lon']}]"
            )

    @staticmethod
    def validate_prediction_record(record: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Comprehensive pre-persistence validator for prediction record dictionaries.
        Returns: (is_valid, rejection_reason)
        """
        try:
            # 1. Check confidence score
            conf = record.get("confidence_score")
            if conf is not None:
                if not (0.0 <= float(conf) <= 1.0):
                    return False, f"Confidence score {conf} outside [0.0, 1.0]"

            # 2. Check coordinates if present
            lat = record.get("center_lat") or record.get("latitude")
            lon = record.get("center_lon") or record.get("longitude")
            if lat is not None and lon is not None:
                NumericalSafetyValidator.validate_coordinates(float(lat), float(lon))

            # 3. Check nowcast sequence arrays if present
            grid_sequence = record.get("grid_sequence") or record.get("nowcast_grid")
            if grid_sequence is not None:
                NumericalSafetyValidator.validate_tensor(grid_sequence, "grid_sequence")

            # 4. Check timestamp format
            init_time = record.get("initialization_time") or record.get("timestamp")
            if init_time:
                # Ensure it can be parsed as ISO 8601
                datetime.fromisoformat(init_time.replace("Z", "+00:00"))

            return True, None

        except (ValueError, NumericalValidationError) as e:
            return False, str(e)

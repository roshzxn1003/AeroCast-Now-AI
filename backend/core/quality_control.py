"""
Atmospheric Data Quality Control (QC) Engine.
Phase 8 Operational Platform — Validates Temporal, Spatial, Numerical & Physical Integrity.
"""
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum
import math
from datetime import datetime, timezone, timedelta
import numpy as np

class QualityFlag(str, Enum):
    VALID = "VALID"
    SUSPECT = "SUSPECT"
    MISSING = "MISSING"
    STALE = "STALE"
    INVALID = "INVALID"

# Physical meteorological boundary definitions for India & Tropical Domains
PHYSICAL_LIMITS = {
    "dbz": {"min": -10.0, "max": 75.0, "unit": "dBZ"},
    "vil": {"min": 0.0, "max": 80.0, "unit": "kg/m²"},
    "tir": {"min": -95.0, "max": 45.0, "unit": "°C"},
    "flash_density": {"min": 0.0, "max": 100.0, "unit": "flashes/km²"},
    "flash_rate": {"min": 0.0, "max": 600.0, "unit": "flashes/min"},
    "cape": {"min": 0.0, "max": 7500.0, "unit": "J/kg"},
    "cin": {"min": -800.0, "max": 50.0, "unit": "J/kg"},
    "wind_shear": {"min": 0.0, "max": 65.0, "unit": "m/s"},
    "lifted_index": {"min": -16.0, "max": 15.0, "unit": "°C"},
    "temperature": {"min": -45.0, "max": 55.0, "unit": "°C"},
    "relative_humidity": {"min": 0.0, "max": 100.0, "unit": "%"},
    "surface_pressure": {"min": 500.0, "max": 1080.0, "unit": "hPa"},
    "wind_speed": {"min": 0.0, "max": 120.0, "unit": "m/s"},
    "precipitable_water": {"min": 0.0, "max": 100.0, "unit": "mm"},
}

# Geographic boundary for Indian Subcontinent & Bay of Bengal / Arabian Sea
INDIA_GEO_BOUNDS = {
    "lat_min": 6.0,
    "lat_max": 38.0,
    "lon_min": 68.0,
    "lon_max": 98.0,
}

@dataclass
class QualityAssessment:
    flag: QualityFlag
    reason: Optional[str] = None
    passed_tests: List[str] = None
    failed_tests: List[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.passed_tests is None:
            self.passed_tests = []
        if self.failed_tests is None:
            self.failed_tests = []
        if self.metadata is None:
            self.metadata = {}

    @property
    def is_usable(self) -> bool:
        return self.flag in (QualityFlag.VALID, QualityFlag.SUSPECT)

class AtmosphericQualityControl:
    """Rigorous multi-stage meteorological quality control."""

    @staticmethod
    def check_temporal(
        obs_time: datetime,
        max_age_minutes: float = 60.0,
        future_tolerance_seconds: float = 60.0,
    ) -> QualityAssessment:
        passed = []
        failed = []

        now = datetime.now(timezone.utc)
        if obs_time.tzinfo is None:
            obs_time = obs_time.replace(tzinfo=timezone.utc)

        age_seconds = (now - obs_time).total_seconds()

        # Check for unphysical future timestamps
        if age_seconds < -future_tolerance_seconds:
            failed.append("temporal_future_timestamp")
            return QualityAssessment(
                flag=QualityFlag.INVALID,
                reason=f"Observation timestamp is in the future by {-age_seconds:.1f}s",
                failed_tests=failed,
                metadata={"age_seconds": age_seconds},
            )
        passed.append("temporal_not_in_future")

        # Check for staleness
        max_age_seconds = max_age_minutes * 60.0
        if age_seconds > max_age_seconds:
            failed.append("temporal_stale")
            return QualityAssessment(
                flag=QualityFlag.STALE,
                reason=f"Observation is stale ({age_seconds / 60.0:.1f} min > {max_age_minutes} min max)",
                passed_tests=passed,
                failed_tests=failed,
                metadata={"age_minutes": age_seconds / 60.0},
            )
        passed.append("temporal_freshness")

        return QualityAssessment(flag=QualityFlag.VALID, passed_tests=passed)

    @staticmethod
    def check_spatial(
        lat: float,
        lon: float,
        require_india_bounds: bool = True,
    ) -> QualityAssessment:
        passed = []
        failed = []

        # Coordinate range checks
        if not (-90.0 <= lat <= 90.0) or math.isnan(lat):
            failed.append("spatial_invalid_latitude")
            return QualityAssessment(
                flag=QualityFlag.INVALID,
                reason=f"Invalid latitude: {lat}",
                failed_tests=failed,
            )
        passed.append("spatial_latitude_valid")

        if not (-180.0 <= lon <= 180.0) or math.isnan(lon):
            failed.append("spatial_invalid_longitude")
            return QualityAssessment(
                flag=QualityFlag.INVALID,
                reason=f"Invalid longitude: {lon}",
                failed_tests=failed,
            )
        passed.append("spatial_longitude_valid")

        # India bounding box check
        if require_india_bounds:
            b = INDIA_GEO_BOUNDS
            if not (b["lat_min"] <= lat <= b["lat_max"] and b["lon_min"] <= lon <= b["lon_max"]):
                failed.append("spatial_outside_domain")
                return QualityAssessment(
                    flag=QualityFlag.SUSPECT,
                    reason=f"Coordinates ({lat:.2f}, {lon:.2f}) outside standard India domain",
                    passed_tests=passed,
                    failed_tests=failed,
                )
            passed.append("spatial_inside_india_bounds")

        return QualityAssessment(flag=QualityFlag.VALID, passed_tests=passed)

    @staticmethod
    def check_numerical(
        value: Any,
        variable: str,
    ) -> QualityAssessment:
        passed = []
        failed = []

        if value is None:
            return QualityAssessment(
                flag=QualityFlag.MISSING,
                reason="Value is None",
                failed_tests=["numerical_present"],
            )

        try:
            val_float = float(value)
        except (ValueError, TypeError):
            return QualityAssessment(
                flag=QualityFlag.INVALID,
                reason=f"Cannot cast value {value} to float",
                failed_tests=["numerical_float_castable"],
            )

        if math.isnan(val_float) or math.isinf(val_float):
            return QualityAssessment(
                flag=QualityFlag.INVALID,
                reason=f"Value is NaN or Infinity: {val_float}",
                failed_tests=["numerical_finite"],
            )
        passed.append("numerical_finite")

        # Physical meteorological limits check
        var_key = variable.lower().strip()
        if var_key in PHYSICAL_LIMITS:
            limits = PHYSICAL_LIMITS[var_key]
            if val_float < limits["min"] or val_float > limits["max"]:
                failed.append("physical_range")
                return QualityAssessment(
                    flag=QualityFlag.INVALID,
                    reason=(
                        f"{variable} value {val_float} exceeds physical limits "
                        f"[{limits['min']}, {limits['max']}] {limits['unit']}"
                    ),
                    passed_tests=passed,
                    failed_tests=failed,
                    metadata={"limits": limits, "value": val_float},
                )
            passed.append("physical_range")

        return QualityAssessment(flag=QualityFlag.VALID, passed_tests=passed)

    @staticmethod
    def check_grid_tensor(
        tensor: np.ndarray,
        expected_shape: tuple = (4, 32, 32, 4),
        max_missing_ratio: float = 0.25,
    ) -> QualityAssessment:
        """Validates 4D spatio-temporal tensor cubes."""
        passed = []
        failed = []

        if not isinstance(tensor, np.ndarray):
            return QualityAssessment(
                flag=QualityFlag.INVALID,
                reason="Input is not a numpy ndarray",
                failed_tests=["tensor_type"],
            )
        passed.append("tensor_type")

        if tensor.shape != expected_shape:
            failed.append("tensor_shape")
            return QualityAssessment(
                flag=QualityFlag.INVALID,
                reason=f"Tensor shape {tensor.shape} != expected {expected_shape}",
                passed_tests=passed,
                failed_tests=failed,
            )
        passed.append("tensor_shape")

        # Check for NaNs and Infs
        nan_count = np.isnan(tensor).sum()
        inf_count = np.isinf(tensor).sum()
        total_elements = tensor.size
        missing_ratio = (nan_count + inf_count) / total_elements

        if missing_ratio > max_missing_ratio:
            failed.append("tensor_missing_ratio")
            return QualityAssessment(
                flag=QualityFlag.INVALID,
                reason=f"Tensor has {missing_ratio * 100:.1f}% missing/NaN values (> {max_missing_ratio * 100:.0f}% tolerance)",
                passed_tests=passed,
                failed_tests=failed,
                metadata={"missing_ratio": missing_ratio},
            )
        elif missing_ratio > 0.0:
            failed.append("tensor_contains_nans")
            return QualityAssessment(
                flag=QualityFlag.SUSPECT,
                reason=f"Tensor contains {nan_count} NaNs ({missing_ratio * 100:.2f}% of grid)",
                passed_tests=passed,
                failed_tests=failed,
                metadata={"missing_ratio": missing_ratio},
            )
        passed.append("tensor_complete_and_finite")

        return QualityAssessment(flag=QualityFlag.VALID, passed_tests=passed)

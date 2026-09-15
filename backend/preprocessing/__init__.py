"""
Preprocessing Package for AeroCast-Now AI Pro
=============================================
Provides:
  - cleaning: Physical limit validation and DataQualityReport scoring
  - interpolation: 15-minute time alignment and gap filling
  - normalization: Min-max scaling for 4 physical channels
  - feature_engineering: 4D spatio-temporal tensor sequence assembly
"""

from preprocessing.cleaning import validate_observation, clean_observation
from preprocessing.interpolation import align_to_15min_cadence, synchronize_time_series
from preprocessing.normalization import (
    normalize_channels,
    denormalize_dbz,
    denormalize_vil,
    denormalize_tir,
    denormalize_flash,
)
from preprocessing.feature_engineering import (
    assemble_spatial_tensor_sequence,
    derive_thermodynamic_sounding,
)

__all__ = [
    "validate_observation",
    "clean_observation",
    "align_to_15min_cadence",
    "synchronize_time_series",
    "normalize_channels",
    "denormalize_dbz",
    "denormalize_vil",
    "denormalize_tir",
    "denormalize_flash",
    "assemble_spatial_tensor_sequence",
    "derive_thermodynamic_sounding",
]

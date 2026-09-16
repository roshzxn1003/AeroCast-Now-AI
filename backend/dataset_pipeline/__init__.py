"""
AeroCast-Now AI — Historical Dataset & Training Pipeline Package
================================================================
Modules for historical data collection, quality control, time synchronization,
spatial regridding (32x32), atmospheric feature engineering, sequence assembly,
chronological splitting, and normalization.
"""

from dataset_pipeline.spatial_grid import regrid_to_32x32, regrid_lightning_strikes, check_missing_pixels
from dataset_pipeline.temporal_sync import align_timestamp_to_15min, resample_time_series_to_15min, assemble_temporal_sequences
from dataset_pipeline.quality_filter import QualityAssessor, QualityFilterResult
from dataset_pipeline.targets import compute_lightning_targets, compute_thunderstorm_target
from dataset_pipeline.scaler import ChannelScaler
from dataset_pipeline.collector import HistoricalDataCollector

__all__ = [
    "regrid_to_32x32",
    "regrid_lightning_strikes",
    "check_missing_pixels",
    "align_timestamp_to_15min",
    "resample_time_series_to_15min",
    "assemble_temporal_sequences",
    "QualityAssessor",
    "QualityFilterResult",
    "compute_lightning_targets",
    "compute_thunderstorm_target",
    "ChannelScaler",
    "HistoricalDataCollector",
]

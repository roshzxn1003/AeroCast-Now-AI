"""
Data Source Adapters Package.
Phase 9 Operational Multi-Source Ingestion & Redundancy.
"""
from ingestion.adapters.base_adapter import DataSourceAdapter
from ingestion.adapters.radar_adapter import (
    IMDDopplerRadarAdapter,
    RainViewerRadarAdapter,
)
from ingestion.adapters.satellite_adapter import (
    INSATSatelliteAdapter,
    OpenMeteoCloudAdapter,
)
from ingestion.adapters.lightning_adapter import (
    BlitzortungLightningAdapter,
    LightningArchiveAdapter,
)
from ingestion.adapters.nwp_adapter import (
    OpenMeteoNWPAdapter,
    ClimatologySoundingAdapter,
)

__all__ = [
    "DataSourceAdapter",
    "IMDDopplerRadarAdapter",
    "RainViewerRadarAdapter",
    "INSATSatelliteAdapter",
    "OpenMeteoCloudAdapter",
    "BlitzortungLightningAdapter",
    "LightningArchiveAdapter",
    "OpenMeteoNWPAdapter",
    "ClimatologySoundingAdapter",
]

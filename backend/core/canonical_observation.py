"""
Canonical Atmospheric Observation Schema.
Phase 9 Operational Data Infrastructure — Provider-Independent Representation.
==============================================================================
Defines the canonical, strongly typed observation contracts for:
  - Scalar observations (point surface & sounding stations)
  - Gridded / Raster observations (Doppler radar, satellite TIR, flash density)
  - Time-series observations (strike rate trends, pressure traces)
  - Storm cell observations (SCIT centroids, convective polygons, motion vectors)

All upstream providers convert their native formats into this canonical representation.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

class ObservationType(str, Enum):
    SCALAR = "SCALAR"
    GRIDDED = "GRIDDED"
    TIME_SERIES = "TIME_SERIES"
    STORM_CELL = "STORM_CELL"

class ProcessingStatus(str, Enum):
    RAW = "RAW"
    NORMALIZED = "NORMALIZED"
    QUALITY_CONTROLLED = "QUALITY_CONTROLLED"
    REGRIDDED = "REGRIDDED"
    FUSED = "FUSED"

class CanonicalQualityFlag(str, Enum):
    VALID = "VALID"
    SUSPECT = "SUSPECT"
    MISSING = "MISSING"
    STALE = "STALE"
    INVALID = "INVALID"
    PARTIAL = "PARTIAL"
    ESTIMATED = "ESTIMATED"

@dataclass
class SpatialDomain:
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float
    resolution_km: float
    crs: str = "EPSG:4326"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class CanonicalProvenance:
    source_provider: str
    source_dataset: str
    source_url_or_channel: Optional[str]
    source_timestamp: str
    ingestion_timestamp: str
    processing_version: str = "2.0.0"
    qc_version: str = "1.0.0"
    regridding_version: str = "1.0.0"
    raw_checksum_sha256: str = ""
    transformation_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class CanonicalObservation:
    """Universal base observation schema."""
    observation_id: str
    obs_type: ObservationType
    source: str                          # e.g., 'IMD', 'RAINVIEWER', 'BLITZORTUNG', 'OPEN_METEO'
    provider: str                        # Adapter name, e.g. 'RadarProvider'
    dataset: str                         # e.g., 'radar_composite', 'insat_tir1', 'lightning_ldn'
    variable: str                        # e.g., 'reflectivity', 'vil', 'brightness_temp', 'cape'
    timestamp: str                       # ISO-8601 UTC observation time
    valid_time: str                      # ISO-8601 UTC valid time
    ingestion_time: str                  # ISO-8601 UTC download time
    unit: str                            # e.g., 'dBZ', 'kg/m²', '°C', 'J/kg', 'flashes/km²'
    quality_flag: CanonicalQualityFlag = CanonicalQualityFlag.VALID
    quality_reason: Optional[str] = None
    processing_status: ProcessingStatus = ProcessingStatus.RAW
    provenance: Optional[CanonicalProvenance] = None
    checksum: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def compute_checksum(self) -> str:
        """Computes SHA-256 integrity hash of this observation's core metadata and value."""
        core = f"{self.source}|{self.dataset}|{self.variable}|{self.timestamp}|{self.valid_time}"
        self.checksum = hashlib.sha256(core.encode("utf-8")).hexdigest()
        return self.checksum

@dataclass
class ScalarObservation(CanonicalObservation):
    """Single point measurement (e.g. AWS temperature, pressure, sounding CAPE)."""
    latitude: float = 0.0
    longitude: float = 0.0
    altitude_m: Optional[float] = None
    value: Optional[float] = None

    def __post_init__(self):
        self.obs_type = ObservationType.SCALAR
        if not self.checksum:
            self.compute_checksum()

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["obs_type"] = self.obs_type.value
        d["quality_flag"] = self.quality_flag.value
        d["processing_status"] = self.processing_status.value
        return d

@dataclass
class GriddedObservation(CanonicalObservation):
    """2D Spatial Raster / Grid observation (e.g. 32x32 radar reflectivity grid)."""
    domain: Optional[SpatialDomain] = None
    grid_shape: Tuple[int, int] = (32, 32)
    grid_data: Optional[np.ndarray] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    mean_value: Optional[float] = None
    missing_mask: Optional[np.ndarray] = None

    def __post_init__(self):
        self.obs_type = ObservationType.GRIDDED
        if self.grid_data is not None and isinstance(self.grid_data, np.ndarray):
            finite_mask = np.isfinite(self.grid_data)
            if np.any(finite_mask):
                self.min_value = float(np.min(self.grid_data[finite_mask]))
                self.max_value = float(np.max(self.grid_data[finite_mask]))
                self.mean_value = float(np.mean(self.grid_data[finite_mask]))
        if not self.checksum:
            self.compute_checksum()

    def compute_checksum(self) -> str:
        sha = hashlib.sha256()
        core = f"{self.source}|{self.dataset}|{self.variable}|{self.timestamp}|{self.grid_shape}"
        sha.update(core.encode("utf-8"))
        if self.grid_data is not None:
            sha.update(self.grid_data.tobytes())
        self.checksum = sha.hexdigest()
        return self.checksum

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["obs_type"] = self.obs_type.value
        d["quality_flag"] = self.quality_flag.value
        d["processing_status"] = self.processing_status.value
        if "grid_data" in d:
            # Don't serialize entire raw numpy arrays into JSON dicts
            d["grid_data"] = None
        if "missing_mask" in d:
            d["missing_mask"] = None
        return d

@dataclass
class TimeSeriesObservation(CanonicalObservation):
    """Time-series observation (e.g. 5-minute flash rate trend)."""
    latitude: float = 0.0
    longitude: float = 0.0
    time_points: List[str] = field(default_factory=list)
    values: List[float] = field(default_factory=list)

    def __post_init__(self):
        self.obs_type = ObservationType.TIME_SERIES
        if not self.checksum:
            self.compute_checksum()

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["obs_type"] = self.obs_type.value
        d["quality_flag"] = self.quality_flag.value
        d["processing_status"] = self.processing_status.value
        return d

@dataclass
class StormCellObservation(CanonicalObservation):
    """Convective storm cell feature (SCIT tracked cell centroid, area, dBZ, motion)."""
    cell_id: str = ""
    centroid_lat: float = 0.0
    centroid_lon: float = 0.0
    area_km2: float = 0.0
    max_dbz: float = 0.0
    mean_dbz: float = 0.0
    max_vil_kg_m2: float = 0.0
    speed_kmh: float = 0.0
    heading_deg: float = 0.0
    severity: str = "MODERATE"
    motion_source: str = "CALCULATED"

    def __post_init__(self):
        self.obs_type = ObservationType.STORM_CELL
        if not self.checksum:
            self.compute_checksum()

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["obs_type"] = self.obs_type.value
        d["quality_flag"] = self.quality_flag.value
        d["processing_status"] = self.processing_status.value
        return d

"""
Base Data Ingestion Classes and Interfaces
==========================================
Defines the standard NormalizedObservation schema, DataQualityReport contract,
and abstract Provider classes for Weather, Radar, Satellite, and Lightning.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


@dataclass
class DataQualityReport:
    """Rigorous scientific data quality and validation assessment."""
    valid: bool
    missing_fields: List[str] = field(default_factory=list)
    source: str = "UNKNOWN"
    timestamp: str = ""
    quality_score: float = 1.0  # 0.0 (unusable) to 1.0 (flawless)
    issues: List[str] = field(default_factory=list)
    is_stale: bool = False
    is_interpolated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NormalizedObservation:
    """
    Standardized internal schema for all incoming surface and sounding observations.
    
    Fields missing from external APIs are set to None (never fabricated).
    Quality and completeness are recorded in the attached `quality` report.
    """
    timestamp: str                  # ISO-8601 UTC
    latitude: float                 # Decimal degrees (-90 to +90)
    longitude: float                # Decimal degrees (-180 to +180)
    station_id: str                 # Unique station identifier
    station_name: str               # Human-readable station name

    # 1. Surface Meteorology
    temperature_c: Optional[float] = None
    relative_humidity_pct: Optional[float] = None
    pressure_hpa: Optional[float] = None
    wind_speed_ms: Optional[float] = None
    wind_direction_deg: Optional[float] = None
    rainfall_mm_h: Optional[float] = None
    cloud_cover_pct: Optional[float] = None

    # 2. Convective Sounding Indices (Thermodynamic Instability)
    cape_j_kg: Optional[float] = None
    cin_j_kg: Optional[float] = None
    lifted_index_c: Optional[float] = None
    precipitable_water_mm: Optional[float] = None
    wind_shear_0_6km_kts: Optional[float] = None
    k_index: Optional[float] = None
    total_totals_index: Optional[float] = None

    # 3. Remote Sensing & Lightning Telemetry
    lightning_count: Optional[int] = None
    lightning_density_flashes_km2: Optional[float] = None
    radar_max_dbz: Optional[float] = None
    vil_kg_m2: Optional[float] = None
    satellite_ir_temperature_c: Optional[float] = None

    # 4. Binary Hazard Indicators (for evaluation/verification)
    thunderstorm_target: Optional[int] = None  # 1 if active storm, 0 if clear, None if unknown
    lightning_target: Optional[int] = None      # 1 if lightning within 15km, 0 if none, None if unknown

    # 5. Provenance and Data Quality
    quality: DataQualityReport = field(
        default_factory=lambda: DataQualityReport(valid=False, source="UNINITIALIZED")
    )
    raw_payload: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if "raw_payload" in d:
            del d["raw_payload"]
        return d


# ==============================================================================
# ABSTRACT DATA PROVIDER INTERFACES
# ==============================================================================

class WeatherDataProvider(ABC):
    """Abstract interface for surface weather and atmospheric sounding data providers."""

    @abstractmethod
    async def fetch_station_observation(
        self,
        station_id: str,
        lat: float,
        lon: float,
        station_name: str = ""
    ) -> NormalizedObservation:
        """Fetch and return the latest normalized station observation."""
        pass

    @abstractmethod
    async def fetch_multi_station_observations(
        self,
        stations: List[Dict[str, Any]]
    ) -> Dict[str, NormalizedObservation]:
        """Fetch observations for multiple stations concurrently."""
        pass


class RadarDataProvider(ABC):
    """Abstract interface for Doppler weather radar providers."""

    @abstractmethod
    async def fetch_radar_grid(
        self,
        station_id: str,
        lat: float,
        lon: float,
        grid_size: int = 32,
        range_km: float = 250.0
    ) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
        """
        Fetches and decodes radar product into:
          - dbz_grid: (grid_size, grid_size) Max Reflectivity (0 to 75 dBZ)
          - vil_grid: (grid_size, grid_size) Vertically Integrated Liquid (0 to 65 kg/m²)
          - metadata: Dict describing extraction, timestamps, and quality
        """
        pass


class SatelliteDataProvider(ABC):
    """Abstract interface for geostationary meteorological satellite providers."""

    @abstractmethod
    async def fetch_satellite_grid(
        self,
        lat: float,
        lon: float,
        grid_size: int = 32,
        domain_deg: float = 2.5
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Fetches and decodes satellite imagery into:
          - tir_grid: (grid_size, grid_size) Thermal IR Brightness Temp (-85°C to +35°C)
          - metadata: Dict describing image resolution, channel, and cloud top statistics
        """
        pass


class LightningDataProvider(ABC):
    """Abstract interface for real-time lightning detection network providers."""

    @abstractmethod
    async def fetch_lightning_strikes(
        self,
        lat: float,
        lon: float,
        radius_km: float = 128.0,
        window_minutes: int = 30
    ) -> List[Dict[str, Any]]:
        """Fetches list of genuine lightning strikes within specified domain."""
        pass

    @abstractmethod
    def calculate_density_grid(
        self,
        strikes: List[Dict[str, Any]],
        center_lat: float,
        center_lon: float,
        grid_size: int = 32,
        domain_radius_km: float = 128.0
    ) -> Tuple[np.ndarray, float, Dict[str, Any]]:
        """
        Aggregates strikes into (grid_size, grid_size) flash density grid (flashes/km²)
        and returns (density_grid, flash_rate_fpm, metadata).
        """
        pass

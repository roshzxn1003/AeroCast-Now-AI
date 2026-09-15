"""
AeroCast-Now Data Ingestion and Pipeline Configuration
======================================================
Centralized configuration management for atmospheric observation data sources,
caching policies, physical validation thresholds, and operational data modes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

DataMode = Literal["simulation", "real", "hybrid"]


@dataclass
class DataConfig:
    """Configuration for data ingestion, caching, and operational mode."""
    
    # Operational Data Mode:
    #   'simulation' -> Pure synthetic convective storm generator (offline/demo/testing)
    #   'real'       -> Pure real observation feeds (fails/flags if sources unavailable)
    #   'hybrid'     -> Fuses live radar, satellite & lightning with baseline models
    data_mode: DataMode = field(
        default_factory=lambda: os.getenv("DATA_MODE", "hybrid").lower()  # type: ignore
    )
    
    # Provider endpoints & keys
    imd_api_url: str = field(
        default_factory=lambda: os.getenv("IMD_API_URL", "https://api.imd.gov.in/public/index.php")
    )
    imd_api_key: str = field(
        default_factory=lambda: os.getenv("IMD_API_KEY", "")
    )
    imd_radar_url: str = field(
        default_factory=lambda: os.getenv("IMD_RADAR_URL", "https://mausam.imd.gov.in/Radar")
    )
    insat_satellite_url: str = field(
        default_factory=lambda: os.getenv("INSAT_SATELLITE_URL", "https://mausam.imd.gov.in/Satellite")
    )
    rainviewer_api_url: str = field(
        default_factory=lambda: os.getenv("RAINVIEWER_API_URL", "https://api.rainviewer.com/public/weather-maps.json")
    )
    open_meteo_url: str = field(
        default_factory=lambda: os.getenv("OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast")
    )
    blitzortung_enabled: bool = field(
        default_factory=lambda: os.getenv("BLITZORTUNG_ENABLED", "true").lower() == "true"
    )
    
    # Directory paths
    base_dir: str = field(
        default_factory=lambda: os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    raw_data_dir: str = field(default="")
    processed_data_dir: str = field(default="")
    datasets_dir: str = field(default="")
    
    # Cache time-to-live (TTL in seconds)
    radar_ttl_s: float = field(
        default_factory=lambda: float(os.getenv("RADAR_TTL_S", "600"))  # 10 min
    )
    satellite_ttl_s: float = field(
        default_factory=lambda: float(os.getenv("SATELLITE_TTL_S", "900"))  # 15 min
    )
    weather_ttl_s: float = field(
        default_factory=lambda: float(os.getenv("WEATHER_TTL_S", "300"))  # 5 min
    )
    lightning_ttl_s: float = field(
        default_factory=lambda: float(os.getenv("LIGHTNING_TTL_S", "180"))  # 3 min
    )
    
    # Grid specifications
    grid_size: int = 32
    domain_radius_km: float = 128.0
    time_steps_history: int = 4
    time_step_interval_min: int = 15

    def __post_init__(self) -> None:
        if not self.raw_data_dir:
            self.raw_data_dir = os.path.join(self.base_dir, "data", "raw")
        if not self.processed_data_dir:
            self.processed_data_dir = os.path.join(self.base_dir, "data", "processed")
        if not self.datasets_dir:
            self.datasets_dir = os.path.join(self.base_dir, "data", "datasets")
            
        # Ensure directories exist
        os.makedirs(self.raw_data_dir, exist_ok=True)
        os.makedirs(self.processed_data_dir, exist_ok=True)
        os.makedirs(self.datasets_dir, exist_ok=True)
        os.makedirs(os.path.join(self.raw_data_dir, "radar"), exist_ok=True)
        os.makedirs(os.path.join(self.raw_data_dir, "satellite"), exist_ok=True)
        os.makedirs(os.path.join(self.raw_data_dir, "weather"), exist_ok=True)
        os.makedirs(os.path.join(self.raw_data_dir, "lightning"), exist_ok=True)

        if self.data_mode not in ("simulation", "real", "hybrid"):
            self.data_mode = "hybrid"


# Global singleton configuration instance
DATA_CONFIG = DataConfig()

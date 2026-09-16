"""
Study Region & Spatial Domain Configuration
============================================
Defines configurable geographical boundaries, spatial grids, and coordinate
transformations for AeroCast-Now AI dataset ingestion and model training.

Defaults to Tamil Nadu / Chennai development domain in India, but allows full
customization via environment variables or CLI arguments without hardcoding.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Any, Tuple
import numpy as np


@dataclass
class StudyRegionConfig:
    """Geographical domain boundaries and spatial grid parameters."""
    
    name: str = field(
        default_factory=lambda: os.getenv("REGION_NAME", "Tamil Nadu / Chennai")
    )
    # Default bounding box for Tamil Nadu / Chennai region:
    # Latitude:  12.0°N to 14.5°N (~278 km North-South)
    # Longitude: 79.0°E to 81.5°E (~270 km East-West)
    min_lat: float = field(
        default_factory=lambda: float(os.getenv("REGION_MIN_LAT", "12.0"))
    )
    max_lat: float = field(
        default_factory=lambda: float(os.getenv("REGION_MAX_LAT", "14.5"))
    )
    min_lon: float = field(
        default_factory=lambda: float(os.getenv("REGION_MIN_LON", "79.0"))
    )
    max_lon: float = field(
        default_factory=lambda: float(os.getenv("REGION_MAX_LON", "81.5"))
    )
    
    # Model spatial grid resolution: 32 x 32 cells
    grid_size: int = field(
        default_factory=lambda: int(os.getenv("REGION_GRID_SIZE", "32"))
    )
    
    # Temporal resolution: 15 minutes target
    temporal_resolution_min: int = field(
        default_factory=lambda: int(os.getenv("TEMPORAL_RESOLUTION_MIN", "15"))
    )

    def __post_init__(self) -> None:
        if self.min_lat >= self.max_lat:
            raise ValueError(f"min_lat ({self.min_lat}) must be less than max_lat ({self.max_lat})")
        if self.min_lon >= self.max_lon:
            raise ValueError(f"min_lon ({self.min_lon}) must be less than max_lon ({self.max_lon})")

    @property
    def center_lat(self) -> float:
        return (self.min_lat + self.max_lat) / 2.0

    @property
    def center_lon(self) -> float:
        return (self.min_lon + self.max_lon) / 2.0

    @property
    def lat_step(self) -> float:
        return (self.max_lat - self.min_lat) / self.grid_size

    @property
    def lon_step(self) -> float:
        return (self.max_lon - self.min_lon) / self.grid_size

    def get_grid_coordinates(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generates 2D arrays (grid_size, grid_size) of latitude and longitude
        corresponding to cell centers.
        """
        lats = np.linspace(self.min_lat, self.max_lat, self.grid_size)
        lons = np.linspace(self.min_lon, self.max_lon, self.grid_size)
        grid_lon, grid_lat = np.meshgrid(lons, lats)
        return grid_lat.astype(np.float32), grid_lon.astype(np.float32)

    def contains_point(self, lat: float, lon: float) -> bool:
        """Checks if a point falls within the study region."""
        return (self.min_lat <= lat <= self.max_lat) and (self.min_lon <= lon <= self.max_lon)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "min_lat": self.min_lat,
            "max_lat": self.max_lat,
            "min_lon": self.min_lon,
            "max_lon": self.max_lon,
            "center_lat": round(self.center_lat, 4),
            "center_lon": round(self.center_lon, 4),
            "grid_size": self.grid_size,
            "temporal_resolution_min": self.temporal_resolution_min,
        }


# Global singleton instance for the active study region
ACTIVE_REGION = StudyRegionConfig()

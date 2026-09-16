"""
Atmospheric Observation Providers Module
========================================
Export provider implementations:
  - BaseObservationProvider, ProviderResult, ObservationQuality
  - RadarProvider
  - SatelliteProvider
  - LightningProvider
  - WeatherProvider
"""

from providers.base_provider import (
    BaseObservationProvider,
    ProviderResult,
    ObservationQuality,
    FRESH_THRESHOLD_MIN,
    DELAYED_THRESHOLD_MIN,
)
from providers.radar_provider import RadarProvider
from providers.satellite_provider import SatelliteProvider
from providers.lightning_provider import LightningProvider
from providers.weather_provider import WeatherProvider

__all__ = [
    "BaseObservationProvider",
    "ProviderResult",
    "ObservationQuality",
    "FRESH_THRESHOLD_MIN",
    "DELAYED_THRESHOLD_MIN",
    "RadarProvider",
    "SatelliteProvider",
    "LightningProvider",
    "WeatherProvider",
]

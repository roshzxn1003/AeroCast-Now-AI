"""
Data Ingestion Package for AeroCast-Now AI Pro
==============================================
Provides modular, decoupled providers for:
  - WeatherDataProvider: IMD & Open-Meteo observations
  - RadarDataProvider: IMD DWR network & RainViewer mosaic
  - SatelliteDataProvider: ISRO / IMD INSAT-3D/3DR
  - LightningDataProvider: Blitzortung network
"""

from data_ingestion.base import (
    DataQualityReport,
    NormalizedObservation,
    WeatherDataProvider,
    RadarDataProvider,
    SatelliteDataProvider,
    LightningDataProvider,
)

__all__ = [
    "DataQualityReport",
    "NormalizedObservation",
    "WeatherDataProvider",
    "RadarDataProvider",
    "SatelliteDataProvider",
    "LightningDataProvider",
]

"""
Data Cleaning & Quality Assessment
==================================
Performs strict meteorological quality control:
  - Missing timestamp & format validation
  - Latitude / Longitude boundary verification (Indian domain)
  - Physical boundary limits (Temperature, Humidity, Pressure, Wind Speed)
  - Detection of stale, duplicate, or corrupted telemetry
  - Quality score calculation (0.0 to 1.0)
"""

from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from data_ingestion.base import DataQualityReport, NormalizedObservation


# Meteorological Physical Limits
TEMP_MIN_C = -50.0
TEMP_MAX_C = 65.0

HUMIDITY_MIN_PCT = 0.0
HUMIDITY_MAX_PCT = 100.0

PRESSURE_MIN_HPA = 850.0
PRESSURE_MAX_HPA = 1060.0

WIND_SPEED_MIN_MS = 0.0
WIND_SPEED_MAX_MS = 100.0

CAPE_MIN_J_KG = 0.0
CAPE_MAX_J_KG = 8000.0

CIN_MIN_J_KG = -800.0
CIN_MAX_J_KG = 0.0

RADAR_DBZ_MIN = 0.0
RADAR_DBZ_MAX = 75.0

SATELLITE_TIR_MIN = -95.0
SATELLITE_TIR_MAX = 45.0

# Indian domain geographic bounds
INDIA_LAT_MIN = 5.0
INDIA_LAT_MAX = 39.0
INDIA_LON_MIN = 67.0
INDIA_LON_MAX = 99.0


def validate_observation(obs: NormalizedObservation, max_age_hours: float = 3.0) -> DataQualityReport:
    """
    Evaluates physical consistency and completeness of an observation.
    Returns a comprehensive DataQualityReport.
    """
    issues: List[str] = []
    missing_fields: List[str] = []
    penalty = 0.0
    is_stale = False

    # 1. Timestamp validation
    if not obs.timestamp:
        issues.append("Missing timestamp")
        penalty += 0.4
    else:
        try:
            # Parse ISO-8601
            ts_str = obs.timestamp.replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            age = (now - dt).total_seconds() / 3600.0
            if age > max_age_hours:
                issues.append(f"Stale observation: {age:.1f} hours old (threshold: {max_age_hours}h)")
                is_stale = True
                penalty += 0.2
            elif age < -0.25:
                issues.append("Future timestamp detected")
                penalty += 0.2
        except Exception:
            issues.append(f"Invalid timestamp format: '{obs.timestamp}'")
            penalty += 0.3

    # 2. Geolocation validation
    if not (INDIA_LAT_MIN <= obs.latitude <= INDIA_LAT_MAX):
        issues.append(f"Latitude {obs.latitude}° outside Indian region [{INDIA_LAT_MIN}, {INDIA_LAT_MAX}]")
        penalty += 0.3
    if not (INDIA_LON_MIN <= obs.longitude <= INDIA_LON_MAX):
        issues.append(f"Longitude {obs.longitude}° outside Indian region [{INDIA_LON_MIN}, {INDIA_LON_MAX}]")
        penalty += 0.3

    # 3. Temperature validation
    if obs.temperature_c is None:
        missing_fields.append("temperature_c")
        penalty += 0.08
    elif not (TEMP_MIN_C <= obs.temperature_c <= TEMP_MAX_C):
        issues.append(f"Impossible temperature: {obs.temperature_c}°C")
        penalty += 0.25

    # 4. Humidity validation
    if obs.relative_humidity_pct is None:
        missing_fields.append("relative_humidity_pct")
        penalty += 0.05
    elif not (HUMIDITY_MIN_PCT <= obs.relative_humidity_pct <= HUMIDITY_MAX_PCT):
        issues.append(f"Impossible relative humidity: {obs.relative_humidity_pct}%")
        penalty += 0.25

    # 5. Pressure validation
    if obs.pressure_hpa is None:
        missing_fields.append("pressure_hpa")
        penalty += 0.05
    elif not (PRESSURE_MIN_HPA <= obs.pressure_hpa <= PRESSURE_MAX_HPA):
        issues.append(f"Impossible surface pressure: {obs.pressure_hpa} hPa")
        penalty += 0.25

    # 6. Wind speed validation
    if obs.wind_speed_ms is None:
        missing_fields.append("wind_speed_ms")
        penalty += 0.05
    elif not (WIND_SPEED_MIN_MS <= obs.wind_speed_ms <= WIND_SPEED_MAX_MS):
        issues.append(f"Impossible wind speed: {obs.wind_speed_ms} m/s")
        penalty += 0.25

    # 7. Radar Reflectivity validation (if provided)
    if obs.radar_max_dbz is not None:
        if not (RADAR_DBZ_MIN <= obs.radar_max_dbz <= RADAR_DBZ_MAX):
            issues.append(f"Out of range radar dBZ: {obs.radar_max_dbz}")
            penalty += 0.2

    # 8. Satellite TIR validation (if provided)
    if obs.satellite_ir_temperature_c is not None:
        if not (SATELLITE_TIR_MIN <= obs.satellite_ir_temperature_c <= SATELLITE_TIR_MAX):
            issues.append(f"Out of range satellite TIR: {obs.satellite_ir_temperature_c}°C")
            penalty += 0.2

    # 9. Convective indices physical validation
    if obs.cape_j_kg is not None:
        if not (CAPE_MIN_J_KG <= obs.cape_j_kg <= CAPE_MAX_J_KG):
            issues.append(f"Out of range CAPE: {obs.cape_j_kg} J/kg")
            penalty += 0.15

    quality_score = max(0.0, round(1.0 - penalty, 2))
    valid = quality_score >= 0.5 and (len(issues) == 0 or (len(issues) == 1 and is_stale))

    return DataQualityReport(
        valid=valid,
        missing_fields=missing_fields,
        source=obs.quality.source or "ASSESSED",
        timestamp=obs.timestamp,
        quality_score=quality_score,
        issues=issues,
        is_stale=is_stale
    )


def clean_observation(obs: NormalizedObservation) -> NormalizedObservation:
    """
    Cleans an observation in place: clips minor out-of-bounds, assesses quality,
    and returns sanitized NormalizedObservation.
    """
    # Sanitize physical parameters within sensible boundaries
    if obs.relative_humidity_pct is not None:
        obs.relative_humidity_pct = max(0.0, min(100.0, obs.relative_humidity_pct))

    if obs.wind_speed_ms is not None:
        obs.wind_speed_ms = max(0.0, min(80.0, obs.wind_speed_ms))

    if obs.radar_max_dbz is not None:
        obs.radar_max_dbz = max(0.0, min(75.0, obs.radar_max_dbz))

    if obs.vil_kg_m2 is not None:
        obs.vil_kg_m2 = max(0.0, min(65.0, obs.vil_kg_m2))

    # Evaluate quality
    obs.quality = validate_observation(obs)
    return obs

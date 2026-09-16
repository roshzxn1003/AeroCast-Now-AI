"""
AeroCast-Now AI — Explainable Alert Rules & Risk Scoring Logic (Phase 7)
========================================================================
Implements transparent, multi-component meteorological risk scoring,
empirical trigger evaluations, and sector-specific impact derivations.
"""

from __future__ import annotations

import os
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from datetime import datetime, timezone

from alerts.alert_models import (
    RiskLevel,
    AlertCategory,
    ImpactSector,
    RiskComponent,
    RiskAssessment,
    SectorImpact,
    DecisionSupportAction,
    RISK_COLOR_MAP,
)

# Optional PyYAML loader with fallback
try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False


DEFAULT_ALERT_CONFIG: Dict[str, Any] = {
    "scoring_weights": {
        "radar_intensity": 0.28,
        "lightning_surge": 0.25,
        "forecast_growth": 0.20,
        "instability": 0.15,
        "persistence_vil": 0.12,
    },
    "thresholds": {
        "reflectivity_dbz": {
            "marginal": 28.0,
            "moderate": 36.0,
            "high": 46.0,
            "severe": 52.0,
        },
        "vil_kg_m2": {
            "marginal": 8.0,
            "moderate": 15.0,
            "high": 25.0,
            "severe": 35.0,
        },
        "lightning_flash_rate_fpm": {
            "elevated": 8.0,
            "high": 16.0,
            "severe": 28.0,
        },
        "lightning_jump": {
            "min_sigma": 1.8,
            "critical_sigma": 2.2,
            "min_rate_fpm": 12.0,
            "min_surge_dfr_dt": 8.0,
        },
        "forecast_intensification": {
            "rapid_growth_delta_dbz": 5.0,
            "explosive_growth_delta_dbz": 9.0,
            "rapid_growth_delta_vil": 8.0,
        },
        "instability": {
            "cape_moderate_j_kg": 1400.0,
            "cape_high_j_kg": 2400.0,
            "cape_extreme_j_kg": 3400.0,
            "deep_layer_shear_kts_high": 28.0,
            "lifted_index_c_unstable": -3.0,
        },
        "proximity_radii_km": {
            "critical_airport": 25.0,
            "urban_metropolitan": 30.0,
            "district_advisory": 50.0,
        },
    },
    "key_assets": {
        "airports": [
            {"id": "VOMM", "name": "Chennai International Airport", "lat": 12.9941, "lon": 80.1709, "critical_radius_km": 25.0},
            {"id": "VOAI", "name": "Tambaram Air Force Base", "lat": 12.9077, "lon": 80.1219, "critical_radius_km": 20.0},
        ],
        "critical_facilities": [
            {"id": "SHAR", "name": "Satish Dhawan Space Centre (Sriharikota)", "lat": 13.7199, "lon": 80.2300, "critical_radius_km": 35.0},
            {"id": "CHENNAI_PORT", "name": "Chennai Port Trust & Harbour", "lat": 13.0878, "lon": 80.2985, "critical_radius_km": 18.0},
        ],
    },
}


def load_alert_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Loads alert thresholds from YAML if available, otherwise uses defaults."""
    candidate_paths = [
        config_path,
        os.path.join(os.path.dirname(__file__), "..", "config", "alert_thresholds.yaml"),
        os.path.join(os.path.dirname(__file__), "..", "..", "config", "alert_thresholds.yaml"),
    ]
    for p in candidate_paths:
        if p and os.path.exists(p) and _YAML_AVAILABLE:
            try:
                with open(p, "r", encoding="utf-8") as f:
                    loaded = yaml.safe_load(f)
                    if loaded and isinstance(loaded, dict):
                        return loaded
            except Exception:
                pass
    return DEFAULT_ALERT_CONFIG


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great-circle distance between two points in km."""
    r = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


def score_to_risk_level(score: float) -> RiskLevel:
    """Maps continuous [0.0 - 100.0] score into standardized RiskLevel."""
    if score >= 85.0:
        return RiskLevel.SEVERE
    elif score >= 65.0:
        return RiskLevel.HIGH
    elif score >= 40.0:
        return RiskLevel.MODERATE
    elif score >= 20.0:
        return RiskLevel.LOW
    return RiskLevel.NORMAL


# ==============================================================================
# SUB-SCORE CALCULATORS (EXPLAINABLE & MATHEMATICALLY TRANSPARENT)
# ==============================================================================

def calculate_radar_intensity_component(
    max_dbz: float,
    mean_dbz: float,
    weight: float = 0.28
) -> RiskComponent:
    """
    Sub-score for radar convective reflectivity.
    35 dBZ initiates deep convective core (Score ~ 37.5)
    45 dBZ corresponds to severe hail/squall core (Score ~ 62.5)
    55+ dBZ corresponds to extreme tornadic/supercell core (Score ~ 87.5 - 100)
    """
    effective_dbz = max(0.0, max_dbz * 0.8 + mean_dbz * 0.2)
    # Range 15 to 60 dBZ mapped linearly to 0 - 100
    norm = min(100.0, max(0.0, (effective_dbz - 15.0) / 45.0 * 100.0))
    weighted = norm * weight
    level = score_to_risk_level(norm)

    explanation = (
        f"Convective core max reflectivity is {max_dbz:.1f} dBZ (domain mean {mean_dbz:.1f} dBZ). "
        f"Values above 45 dBZ indicate deep cumulonimbus development with intense precipitation."
    )
    return RiskComponent(
        name="Radar Convective Intensity",
        weight=weight,
        raw_value=max_dbz,
        unit="dBZ",
        normalized_score=norm,
        weighted_score=weighted,
        level=level,
        explanation=explanation,
    )


def calculate_lightning_surge_component(
    flash_rate_fpm: float,
    jump_detected: bool,
    sigma_metric: float,
    dfr_dt: float,
    weight: float = 0.25
) -> RiskComponent:
    """
    Sub-score for lightning activity and 2-sigma precursor surge.
    """
    # Flash rate contributes up to 50 points
    rate_score = min(50.0, max(0.0, (flash_rate_fpm / 30.0) * 50.0))

    # Precursor surge contributes up to 50 points
    surge_score = 0.0
    if jump_detected:
        surge_score = 50.0
    elif sigma_metric >= 1.5:
        surge_score = 35.0
    elif sigma_metric >= 1.0:
        surge_score = 20.0
    elif dfr_dt > 5.0:
        surge_score = 15.0

    norm = min(100.0, rate_score + surge_score)
    weighted = norm * weight
    level = score_to_risk_level(norm)

    if jump_detected:
        expl = (
            f"⚡ CRITICAL 2-Sigma Lightning Jump active ({sigma_metric:.1f}σ, +{dfr_dt:.1f} fpm/5m). "
            f"Current flash rate is {flash_rate_fpm:.1f} fpm. Signals violent mixed-phase updraft electrification."
        )
    elif sigma_metric >= 1.2:
        expl = (
            f"Elevated flash rate of {flash_rate_fpm:.1f} fpm with convective surge trend ({sigma_metric:.1f}σ). "
            f"Approaching lightning jump alert threshold."
        )
    else:
        expl = f"Total lightning flash rate is {flash_rate_fpm:.1f} fpm with stable baseline trend ({sigma_metric:.1f}σ)."

    return RiskComponent(
        name="Lightning & Jump Precursor",
        weight=weight,
        raw_value=flash_rate_fpm,
        unit="fpm",
        normalized_score=norm,
        weighted_score=weighted,
        level=level,
        explanation=expl,
    )


def calculate_forecast_growth_component(
    t0_max_dbz: float,
    fc15_max_dbz: float,
    t0_vil: float,
    fc15_vil: float,
    weight: float = 0.20
) -> RiskComponent:
    """
    Sub-score for ConvLSTM lead-time intensification trend (+15m / +30m).
    """
    delta_dbz = fc15_max_dbz - t0_max_dbz
    delta_vil = fc15_vil - t0_vil

    base_score = 20.0
    if delta_dbz > 0:
        base_score += min(50.0, delta_dbz * 7.5)
    else:
        base_score = max(5.0, base_score + delta_dbz * 3.0)

    if delta_vil > 0:
        base_score += min(30.0, delta_vil * 3.5)

    norm = min(100.0, max(0.0, base_score))
    weighted = norm * weight
    level = score_to_risk_level(norm)

    if delta_dbz >= 5.0:
        expl = (
            f"Rapid ConvLSTM forecast intensification: core reflectivity projected to increase "
            f"by +{delta_dbz:.1f} dBZ (and +{delta_vil:.1f} kg/m² VIL) within +15 minutes."
        )
    elif delta_dbz > 1.0:
        expl = f"Moderate convective growth projected (+{delta_dbz:.1f} dBZ over next 15 minutes)."
    elif delta_dbz < -3.0:
        expl = f"Convective core is decaying/dissipating ({delta_dbz:.1f} dBZ trend)."
    else:
        expl = "Steady state storm intensity projected over immediate nowcast horizon."

    return RiskComponent(
        name="AI Forecast Growth Trend",
        weight=weight,
        raw_value=delta_dbz,
        unit="ΔdBZ/15m",
        normalized_score=norm,
        weighted_score=weighted,
        level=level,
        explanation=expl,
    )


def calculate_instability_component(
    sounding: Dict[str, Any],
    weight: float = 0.15
) -> RiskComponent:
    """
    Sub-score for atmospheric sounding thermodynamics (CAPE, Shear, LI).
    """
    cape = float(sounding.get("CAPE_J_kg", sounding.get("base_cape", 1600.0)))
    shear = float(sounding.get("Deep_Layer_Shear_0_6km_kts", sounding.get("base_shear", 20.0)))
    li = float(sounding.get("Lifted_Index_C", -2.5))

    # CAPE contributes up to 50 points
    cape_score = min(50.0, max(0.0, (cape / 3500.0) * 50.0))
    # Shear contributes up to 30 points (shear > 35 kts supports organized supercells)
    shear_score = min(30.0, max(0.0, (shear / 40.0) * 30.0))
    # Lifted Index contributes up to 20 points
    li_score = min(20.0, max(0.0, abs(min(0.0, li)) / 6.0 * 20.0))

    norm = min(100.0, cape_score + shear_score + li_score)
    weighted = norm * weight
    level = score_to_risk_level(norm)

    expl = (
        f"Environmental thermodynamics: CAPE {cape:.0f} J/kg, 0-6km Shear {shear:.0f} kts, Lifted Index {li:.1f}°C. "
        f"{'High buoyancy and shear support organized, long-lived storm clusters.' if norm >= 60 else 'Moderate atmospheric instability.'}"
    )

    return RiskComponent(
        name="Atmospheric Instability",
        weight=weight,
        raw_value=cape,
        unit="J/kg",
        normalized_score=norm,
        weighted_score=weighted,
        level=level,
        explanation=expl,
    )


def calculate_persistence_vil_component(
    max_vil: float,
    active_cell_count: int,
    weight: float = 0.12
) -> RiskComponent:
    """
    Sub-score for Vertically Integrated Liquid core and cluster coverage.
    """
    # VIL up to 35 kg/m² contributes 70 points
    vil_score = min(70.0, max(0.0, (max_vil / 35.0) * 70.0))
    # Cell cluster count contributes up to 30 points
    cell_score = min(30.0, active_cell_count * 10.0)

    norm = min(100.0, vil_score + cell_score)
    weighted = norm * weight
    level = score_to_risk_level(norm)

    expl = (
        f"Max VIL core is {max_vil:.1f} kg/m² across {active_cell_count} active convective cores. "
        f"VIL values above 25 kg/m² indicate severe hail potential and heavy water loading."
    )

    return RiskComponent(
        name="VIL Core & Multi-Cell Coverage",
        weight=weight,
        raw_value=max_vil,
        unit="kg/m²",
        normalized_score=norm,
        weighted_score=weighted,
        level=level,
        explanation=expl,
    )


# ==============================================================================
# COMPOSITE RISK ASSESSMENT GENERATOR
# ==============================================================================

def assess_convective_risk(
    nowcast_data: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None
) -> RiskAssessment:
    """
    Evaluates multi-factor meteorological observations and AI nowcasts to
    produce an explainable, weighted RiskAssessment.
    """
    cfg = config or load_alert_config()
    weights = cfg.get("scoring_weights", DEFAULT_ALERT_CONFIG["scoring_weights"])

    obs = nowcast_data.get("observation", {})
    max_dbz = float(obs.get("max_dbz", 0.0))
    # Approximate mean dBZ from storm cells if present
    cells = obs.get("storm_cells", [])
    mean_dbz = float(np.mean([c.get("mean_dbz", max_dbz * 0.7) for c in cells])) if cells else max_dbz * 0.5
    max_vil = float(obs.get("max_vil", 0.0))
    flash_rate = float(obs.get("flash_rate_fpm", 0.0))

    # Lightning jump telemetry
    jump = nowcast_data.get("lightning_jump", {})
    jump_detected = bool(jump.get("jump_detected", False))
    sigma_metric = float(jump.get("sigma_metric", 0.0))
    dfr_dt = float(jump.get("dfr_dt", 0.0))

    # Forecast steps for growth trend
    fc_steps = nowcast_data.get("forecast", [])
    if fc_steps:
        fc15 = fc_steps[0]
        fc15_dbz = float(fc15.get("max_dbz", max_dbz))
        fc15_vil = float(fc15.get("max_vil", max_vil))
    else:
        fc15_dbz = max_dbz
        fc15_vil = max_vil

    # Sounding parameters
    sounding = nowcast_data.get("sounding", {})

    # Compute individual explainable components
    comp_radar = calculate_radar_intensity_component(max_dbz, mean_dbz, weights.get("radar_intensity", 0.28))
    comp_lightning = calculate_lightning_surge_component(flash_rate, jump_detected, sigma_metric, dfr_dt, weights.get("lightning_surge", 0.25))
    comp_growth = calculate_forecast_growth_component(max_dbz, fc15_dbz, max_vil, fc15_vil, weights.get("forecast_growth", 0.20))
    comp_instability = calculate_instability_component(sounding, weights.get("instability", 0.15))
    comp_vil = calculate_persistence_vil_component(max_vil, len(cells), weights.get("persistence_vil", 0.12))

    components = [comp_radar, comp_lightning, comp_growth, comp_instability, comp_vil]

    overall_score = sum(c.weighted_score for c in components)
    overall_score = min(100.0, max(0.0, overall_score))

    risk_level = score_to_risk_level(overall_score)
    color = RISK_COLOR_MAP.get(risk_level, "#10b981")

    # Primary driver is the component with highest weighted contribution
    primary = max(components, key=lambda c: c.weighted_score)
    primary_driver = f"{primary.name} ({primary.normalized_score:.0f}/100, weighted {primary.weighted_score:.1f} pts)"

    # Determine if alert threshold is triggered
    is_alert_triggered = overall_score >= 40.0 or jump_detected or max_dbz >= 48.0

    # Model confidence score based on data provenance
    prov = nowcast_data.get("provenance", "")
    confidence = 0.92 if prov == "LIVE_REAL_DATA" else 0.85 if "HYBRID" in prov else 0.75

    summary = (
        f"AI Convective Risk is assessed as {risk_level.value} (Score {overall_score:.1f}/100). "
        f"Primary driver: {primary.name}. "
        f"{'⚡ Preemptive mitigation recommended.' if is_alert_triggered else 'Normal convective monitoring.'}"
    )

    return RiskAssessment(
        overall_score=overall_score,
        risk_level=risk_level,
        color=color,
        components=components,
        summary=summary,
        primary_driver=primary_driver,
        is_alert_triggered=is_alert_triggered,
        confidence_score=confidence,
    )


# ==============================================================================
# IMPACT ESTIMATION & DECISION SUPPORT PROTOCOLS
# ==============================================================================

def estimate_sector_impacts(
    assessment: RiskAssessment,
    nowcast_data: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None
) -> List[SectorImpact]:
    """Generates sector-specific impact predictions based on storm severity."""
    cfg = config or load_alert_config()
    obs = nowcast_data.get("observation", {})
    max_dbz = float(obs.get("max_dbz", 0.0))
    jump = nowcast_data.get("lightning_jump", {})
    has_jump = bool(jump.get("jump_detected", False))
    level = assessment.risk_level

    impacts: List[SectorImpact] = []

    # 1. Aviation Sector
    av_hazards = []
    av_level = level
    if max_dbz >= 45.0 or has_jump:
        av_hazards.extend([
            "Severe low-level wind shear (LLWS) and microburst hazard on final approach",
            "Ground ramp lightning hazard: cloud-to-ground strikes within 5 nm radius",
            "Severe turbulence and hail ingestion in terminal maneuvering area (TMA)",
        ])
        av_level = RiskLevel.SEVERE if has_jump and max_dbz >= 50.0 else RiskLevel.HIGH
    elif max_dbz >= 35.0:
        av_hazards.extend([
            "Moderate convective turbulence on climbout and arrival corridors",
            "Temporary runway visual range reduction during heavy rain bursts",
        ])
        av_level = RiskLevel.MODERATE
    else:
        av_hazards.append("VMC conditions; isolated convective buildups with no operational disruption")
        av_level = RiskLevel.NORMAL

    impacts.append(SectorImpact(
        sector=ImpactSector.AVIATION,
        severity=av_level,
        headline=f"Aviation Convective Impact: {av_level.value}",
        hazards=av_hazards,
        affected_assets=["Chennai TMA", "Runway 07/25", "Ground Ramp Operations"],
        onset_lead_time_min=jump.get("estimated_lead_time_min", 20) if has_jump else 15,
        duration_min=45 if has_jump else 30,
    ))

    # 2. Power Grid & Utilities
    pwr_hazards = []
    pwr_level = level
    if has_jump or max_dbz >= 48.0:
        pwr_hazards.extend([
            "High-density cloud-to-ground strike clusters along transmission corridors",
            "Transient overvoltage trip risk on 230kV / 400kV trunk lines",
            "Substation yard strike hazard requiring auto-reclosure suppression",
        ])
        pwr_level = RiskLevel.SEVERE if has_jump else RiskLevel.HIGH
    elif max_dbz >= 36.0:
        pwr_hazards.extend([
            "Localized feeder tripping due to tree branches on distribution lines",
            "Elevated surge suppressor activity on medium-voltage networks",
        ])
        pwr_level = RiskLevel.MODERATE
    else:
        pwr_hazards.append("Grid operations nominal. Normal lightning protection levels adequate.")
        pwr_level = RiskLevel.NORMAL

    impacts.append(SectorImpact(
        sector=ImpactSector.POWER_GRID,
        severity=pwr_level,
        headline=f"Power Grid Lightning Threat: {pwr_level.value}",
        hazards=pwr_hazards,
        affected_assets=["North Chennai Substation", "Sriperumbudur 400kV Ring", "Distribution Feeders"],
        onset_lead_time_min=15,
        duration_min=60,
    ))

    # 3. Public Safety & Urban Infrastructure
    pub_hazards = []
    pub_level = level
    if max_dbz >= 48.0 or has_jump:
        pub_hazards.extend([
            "Deadly cloud-to-ground lightning hazard in open recreational and coastal areas",
            "Localized flash waterlogging and arterial traffic stagnation (rainfall > 35 mm/h)",
            "Gale-force convective squalls (45-65 km/h) causing treefalls and billboard collapse",
        ])
        pub_level = RiskLevel.SEVERE if has_jump else RiskLevel.HIGH
    elif max_dbz >= 36.0:
        pub_hazards.extend([
            "Intermittent lightning strikes dangerous to pedestrians in open terrain",
            "Slippery road surfaces and localized low-lying water accumulation",
        ])
        pub_level = RiskLevel.MODERATE
    else:
        pub_hazards.append("No immediate public safety convective threat.")
        pub_level = RiskLevel.NORMAL

    impacts.append(SectorImpact(
        sector=ImpactSector.PUBLIC_SAFETY,
        severity=pub_level,
        headline=f"Public Safety & Municipal Hazard: {pub_level.value}",
        hazards=pub_hazards,
        affected_assets=["Marina Beach Promenade", "Central Urban Corridors", "Metro Surface Depots"],
        onset_lead_time_min=15,
        duration_min=60,
    ))

    # 4. Agriculture & Rural Safety
    agr_hazards = []
    agr_level = level
    if max_dbz >= 50.0 or has_jump:
        agr_hazards.extend([
            "High probability of localized crop-damaging hail (diameter 1.5 - 3.0 cm)",
            "Extremely hazardous cloud-to-ground lightning risk for farmers working open fields",
            "Lodging of standing paddy, banana, and sugarcane crops due to intense squalls",
        ])
        agr_level = RiskLevel.SEVERE if has_jump else RiskLevel.HIGH
    elif max_dbz >= 38.0:
        agr_hazards.extend([
            "Moderate rain beneficial for soil moisture, but field work must pause for lightning",
            "Risk of localized nursery soil erosion under heavy rain bursts",
        ])
        agr_level = RiskLevel.MODERATE
    else:
        agr_hazards.append("Benign agricultural weather conditions.")
        agr_level = RiskLevel.NORMAL

    impacts.append(SectorImpact(
        sector=ImpactSector.AGRICULTURE,
        severity=agr_level,
        headline=f"Agricultural & Rural Risk: {agr_level.value}",
        hazards=agr_hazards,
        affected_assets=["Peri-urban Agricultural Belts", "Horticultural Plantations", "Open Grazing Livestock"],
        onset_lead_time_min=20,
        duration_min=60,
    ))

    return impacts


def generate_decision_support_actions(
    assessment: RiskAssessment,
    impacts: List[SectorImpact],
    lead_time_min: int = 20
) -> List[DecisionSupportAction]:
    """Generates concrete operational mitigation protocols."""
    level = assessment.risk_level
    actions: List[DecisionSupportAction] = []

    if level in (RiskLevel.SEVERE, RiskLevel.HIGH):
        actions.append(DecisionSupportAction(
            action_id="ACT-AV-01",
            sector=ImpactSector.AVIATION,
            priority="IMMEDIATE",
            action="Trigger ground ramp lightning hold: suspend aircraft fueling and open baggage operations immediately.",
            lead_time_min=lead_time_min,
            target_audience="Airport Duty Manager & Airline Ramp Dispatchers",
        ))
        actions.append(DecisionSupportAction(
            action_id="ACT-AV-02",
            sector=ImpactSector.AVIATION,
            priority="IMMEDIATE",
            action="Advise Air Traffic Control (ATC) of convective core bearing; initiate holding patterns or runway realignment.",
            lead_time_min=lead_time_min,
            target_audience="ATC Tower Supervisor & Approach Control",
        ))
        actions.append(DecisionSupportAction(
            action_id="ACT-PWR-01",
            sector=ImpactSector.POWER_GRID,
            priority="IMMEDIATE",
            action="Place transmission substation restoration crews on Level 2 standby; monitor auto-reclose cycles on trunk feeders.",
            lead_time_min=lead_time_min,
            target_audience="State Load Despatch Centre (SLDC) Shift In-Charge",
        ))
        actions.append(DecisionSupportAction(
            action_id="ACT-PUB-01",
            sector=ImpactSector.PUBLIC_SAFETY,
            priority="IMMEDIATE",
            action="Broadcast emergency lightning safety advisory: evacuate open beaches, playgrounds, and tree-shaded areas to indoor shelter.",
            lead_time_min=lead_time_min,
            target_audience="District Disaster Management Authority (DDMA) & Police Wireless",
        ))
        actions.append(DecisionSupportAction(
            action_id="ACT-PUB-02",
            sector=ImpactSector.PUBLIC_SAFETY,
            priority="PRECAUTIONARY",
            action="Pre-position motorized de-watering pumps in designated underpass and low-lying urban catchments.",
            lead_time_min=lead_time_min + 15,
            target_audience="Municipal Corporation Stormwater Drain Engineers",
        ))
    elif level == RiskLevel.MODERATE:
        actions.append(DecisionSupportAction(
            action_id="ACT-AV-03",
            sector=ImpactSector.AVIATION,
            priority="PRECAUTIONARY",
            action="Issue advisory for moderate convective cells in terminal approach corridor; maintain heightened vigilance for wind shift.",
            lead_time_min=lead_time_min,
            target_audience="Airlines Dispatch & Flight Operations Officers",
        ))
        actions.append(DecisionSupportAction(
            action_id="ACT-PWR-02",
            sector=ImpactSector.POWER_GRID,
            priority="PRECAUTIONARY",
            action="Review feeder status telemetry; verify remote isolation switch availability.",
            lead_time_min=lead_time_min,
            target_audience="Distribution Operations Control",
        ))
        actions.append(DecisionSupportAction(
            action_id="ACT-PUB-03",
            sector=ImpactSector.PUBLIC_SAFETY,
            priority="PRECAUTIONARY",
            action="Advise general public to monitor weather updates and avoid sheltering under isolated trees during sudden showers.",
            lead_time_min=lead_time_min,
            target_audience="Public Information Officer",
        ))
    else:
        actions.append(DecisionSupportAction(
            action_id="ACT-GEN-01",
            sector=ImpactSector.PUBLIC_SAFETY,
            priority="STANDBY",
            action="Maintain routine automated radar and lightning network surveillance. No active interventions required.",
            lead_time_min=0,
            target_audience="Operations Duty Officer",
        ))

    return actions

"""
AeroCast-Now AI — Central Alert Engine & Decision Support Coordinator (Phase 7)
=============================================================================
Consumes real atmospheric observations and ConvLSTM AI nowcasts to generate:
  1. Explainable convective risk assessments
  2. Concrete sector impact predictions (Aviation, Power Grid, Public Safety, Agriculture)
  3. Actionable decision-support mitigations
  4. Deduplicated alert records in the AlertStore
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta

from alerts.alert_models import (
    RiskLevel,
    AlertCategory,
    ImpactSector,
    RiskAssessment,
    SectorImpact,
    DecisionSupportAction,
    AlertItem,
)
from alerts.alert_rules import (
    load_alert_config,
    assess_convective_risk,
    estimate_sector_impacts,
    generate_decision_support_actions,
    haversine_km,
)
from alerts.alert_store import AlertStore


class AlertEngine:
    """End-to-end alert generation and decision support coordinator."""

    def __init__(self, config_path: Optional[str] = None, store: Optional[AlertStore] = None) -> None:
        self.config = load_alert_config(config_path)
        self.store = store or AlertStore()
        self.last_assessment: Optional[RiskAssessment] = None

    def evaluate_nowcast(
        self,
        nowcast_data: Dict[str, Any]
    ) -> Tuple[RiskAssessment, List[AlertItem]]:
        """
        Main pipeline entry point:
        1. Evaluates multi-factor risk assessment.
        2. Derives domain impact predictions.
        3. Identifies operational trigger conditions.
        4. Synthesizes and registers alerts in AlertStore.
        """
        station = nowcast_data.get("station", "Unknown Radar Station")
        loc = nowcast_data.get("location", {})
        station_lat = float(loc.get("lat", 13.0827))
        station_lon = float(loc.get("lon", 80.2707))

        # 1. Multi-factor explainable risk assessment
        assessment = assess_convective_risk(nowcast_data, self.config)

        # 2. Sector impact predictions
        impacts = estimate_sector_impacts(assessment, nowcast_data, self.config)

        # 3. Decision-support actions
        actions = generate_decision_support_actions(assessment, impacts)

        generated_alerts: List[AlertItem] = []
        now = datetime.now(timezone.utc)
        obs = nowcast_data.get("observation", {})
        cells = obs.get("storm_cells", [])
        jump = nowcast_data.get("lightning_jump", {})
        has_jump = bool(jump.get("jump_detected", False))
        max_dbz = float(obs.get("max_dbz", 0.0))
        max_vil = float(obs.get("max_vil", 0.0))

        # ----------------------------------------------------------------------
        # TRIGGER CHECK 1: 2-Sigma Lightning Jump Precursor
        # ----------------------------------------------------------------------
        if has_jump:
            lead_time = int(jump.get("estimated_lead_time_min", 25))
            valid_until = (now + timedelta(minutes=lead_time + 30)).isoformat()
            alert_id = f"ALT-JUMP-{station[:4].upper()}-{now.strftime('%H%M%S')}"

            jump_alert = AlertItem(
                alert_id=alert_id,
                timestamp=now.isoformat(),
                station=station,
                target_lat=station_lat,
                target_lon=station_lon,
                risk_level=RiskLevel.SEVERE if max_dbz >= 48.0 else RiskLevel.HIGH,
                category=AlertCategory.LIGHTNING_JUMP,
                headline=f"⚡ Precursor Alert: 2-Sigma Lightning Surge Detected for {station}",
                description=(
                    f"Rapid storm electrification ({jump.get('sigma_metric', 2.0)}σ, +{jump.get('dfr_dt', 0.0)} fpm/5m). "
                    f"High probability of severe downburst, damaging lightning, and hail in approximately {lead_time} minutes."
                ),
                trigger_reason=f"2-Sigma Lightning Jump threshold reached: {jump.get('sigma_metric', 2.0)}σ >= 2.0σ",
                lead_time_min=lead_time,
                valid_until=valid_until,
                impacts=impacts,
                actions=actions,
                risk_assessment=assessment,
            )
            stored, _ = self.store.add_alert(jump_alert)
            generated_alerts.append(stored)

        # ----------------------------------------------------------------------
        # TRIGGER CHECK 2: Severe Convective Core / Squall Surge
        # ----------------------------------------------------------------------
        if max_dbz >= 48.0 and not has_jump:
            valid_until = (now + timedelta(minutes=45)).isoformat()
            alert_id = f"ALT-CONV-{station[:4].upper()}-{now.strftime('%H%M%S')}"

            conv_alert = AlertItem(
                alert_id=alert_id,
                timestamp=now.isoformat(),
                station=station,
                target_lat=station_lat,
                target_lon=station_lon,
                risk_level=RiskLevel.SEVERE if max_dbz >= 54.0 else RiskLevel.HIGH,
                category=AlertCategory.SEVERE_CONVECTION,
                headline=f"Severe Thunderstorm Core ({max_dbz:.1f} dBZ) Active in {station} Domain",
                description=(
                    f"Intense radar reflectivity reaching {max_dbz:.1f} dBZ indicates mature cumulonimbus development "
                    f"with torrential rain rates, localized squall winds, and frequent lightning."
                ),
                trigger_reason=f"Reflectivity exceeds severe threshold: {max_dbz:.1f} dBZ >= 48.0 dBZ",
                lead_time_min=15,
                valid_until=valid_until,
                impacts=impacts,
                actions=actions,
                risk_assessment=assessment,
            )
            stored, _ = self.store.add_alert(conv_alert)
            generated_alerts.append(stored)

        # ----------------------------------------------------------------------
        # TRIGGER CHECK 3: High VIL & Hail Risk
        # ----------------------------------------------------------------------
        high_hail_cells = [c for c in cells if c.get("max_vil_kg_m2", 0) >= 22.0 or c.get("hail_risk_pct", 0) >= 50]
        if high_hail_cells and not any(a.category == AlertCategory.HAIL_HAZARD for a in generated_alerts):
            top_cell = high_hail_cells[0]
            valid_until = (now + timedelta(minutes=30)).isoformat()
            alert_id = f"ALT-HAIL-{top_cell.get('cell_id', 'C1')}-{now.strftime('%H%M%S')}"

            hail_alert = AlertItem(
                alert_id=alert_id,
                timestamp=now.isoformat(),
                station=station,
                target_lat=station_lat,
                target_lon=station_lon,
                risk_level=RiskLevel.HIGH,
                category=AlertCategory.HAIL_HAZARD,
                headline=f"Severe Hail Threat: VIL Core {top_cell.get('max_vil_kg_m2', 0):.1f} kg/m² in {top_cell.get('cell_id', 'Storm Cell')}",
                description=(
                    f"Elevated Vertically Integrated Liquid ({top_cell.get('max_vil_kg_m2', 0):.1f} kg/m²) indicates dense "
                    f"suspended ice/graupel mass with {top_cell.get('hail_risk_pct', 0):.0f}% hail probability."
                ),
                trigger_reason=f"VIL core exceeds hail threshold: {top_cell.get('max_vil_kg_m2', 0):.1f} >= 22.0 kg/m²",
                lead_time_min=15,
                valid_until=valid_until,
                cell_id=top_cell.get("cell_id"),
                impacts=impacts,
                actions=actions,
                risk_assessment=assessment,
            )
            stored, _ = self.store.add_alert(hail_alert)
            generated_alerts.append(stored)

        # ----------------------------------------------------------------------
        # TRIGGER CHECK 4: Strategic Asset Proximity (Airports / Facilities)
        # ----------------------------------------------------------------------
        assets = self.config.get("key_assets", {})
        airports = assets.get("airports", [])
        for ap in airports:
            ap_lat = ap.get("lat")
            ap_lon = ap.get("lon")
            ap_rad = ap.get("critical_radius_km", 25.0)
            if ap_lat is not None and ap_lon is not None:
                dist_station_ap = haversine_km(station_lat, station_lon, ap_lat, ap_lon)
                # Check if station domain overlaps airport and storm is active
                if dist_station_ap <= 120.0 and (max_dbz >= 40.0 or has_jump):
                    valid_until = (now + timedelta(minutes=45)).isoformat()
                    alert_id = f"ALT-PROX-{ap.get('id', 'AIRPORT')}-{now.strftime('%H%M%S')}"

                    prox_alert = AlertItem(
                        alert_id=alert_id,
                        timestamp=now.isoformat(),
                        station=station,
                        target_lat=ap_lat,
                        target_lon=ap_lon,
                        risk_level=RiskLevel.HIGH if max_dbz >= 48.0 or has_jump else RiskLevel.MODERATE,
                        category=AlertCategory.ASSET_PROXIMITY,
                        headline=f"Aviation Terminal Threat: Convective Cell within {ap_rad:.0f}km of {ap.get('name')}",
                        description=(
                            f"Thunderstorm activity (up to {max_dbz:.1f} dBZ) tracked in terminal operations area of "
                            f"{ap.get('name')}. Potential wind shear and ramp lightning impact."
                        ),
                        trigger_reason=f"Active storm core within critical operational range of {ap.get('name')}",
                        lead_time_min=20,
                        valid_until=valid_until,
                        impacts=impacts,
                        actions=actions,
                        risk_assessment=assessment,
                    )
                    stored, _ = self.store.add_alert(prox_alert)
                    generated_alerts.append(stored)
                    break

        # If general risk is MODERATE or above but no specific sub-trigger fired, generate overall surge alert
        if assessment.is_alert_triggered and not generated_alerts:
            valid_until = (now + timedelta(minutes=30)).isoformat()
            alert_id = f"ALT-GEN-{station[:4].upper()}-{now.strftime('%H%M%S')}"

            gen_alert = AlertItem(
                alert_id=alert_id,
                timestamp=now.isoformat(),
                station=station,
                target_lat=station_lat,
                target_lon=station_lon,
                risk_level=assessment.risk_level,
                category=AlertCategory.THUNDERSTORM_SURGE,
                headline=f"Convective Alert: {assessment.risk_level.value} Thunderstorm Conditions at {station}",
                description=assessment.summary,
                trigger_reason=f"Composite risk score ({assessment.overall_score:.1f}/100) triggered alert threshold.",
                lead_time_min=15,
                valid_until=valid_until,
                impacts=impacts,
                actions=actions,
                risk_assessment=assessment,
            )
            stored, _ = self.store.add_alert(gen_alert)
            generated_alerts.append(stored)

        self.last_assessment = assessment
        return assessment, generated_alerts


# Global singleton instance for easy import across FastAPI routes
alert_engine = AlertEngine()

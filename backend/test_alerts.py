"""
AeroCast-Now AI — Phase 7: Alert Engine Unit Tests
===================================================
Tests for alert_models, alert_rules scoring, alert_store lifecycle, and alert_engine.
"""

import sys
import os
import unittest
from datetime import datetime, timezone, timedelta

# Ensure backend is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from alerts.alert_models import (
    RiskLevel,
    AlertCategory,
    ImpactSector,
    RiskComponent,
    RiskAssessment,
    SectorImpact,
    DecisionSupportAction,
    AlertItem,
    RISK_COLOR_MAP,
)
from alerts.alert_store import AlertStore
from alerts.alert_rules import (
    load_alert_config,
    assess_convective_risk,
    estimate_sector_impacts,
    generate_decision_support_actions,
    haversine_km,
)
from alerts.alert_engine import AlertEngine


# ==============================================================================
# Helper: Build a realistic nowcast payload for testing
# ==============================================================================

def _make_nowcast(max_dbz=58.0, max_vil=44.0, flash_rate=76.0, has_jump=True,
                  sigma=3.4, cape=2500, shear=22, station="Chennai DWR (Sriharikota/Port)"):
    """Build a realistic nowcast payload matching what the API would produce."""
    return {
        "station": station,
        "location": {"lat": 13.0827, "lon": 80.2707},
        "state": "Tamil Nadu",
        "observation": {
            "max_dbz": max_dbz,
            "max_vil": max_vil,
            "min_tir_c": -72.0,
            "flash_rate_fpm": flash_rate,
            "storm_cells": [
                {
                    "cell_id": "CELL-01",
                    "centroid_pixel": [18.4, 14.2],
                    "max_dbz": max_dbz,
                    "mean_dbz": max_dbz * 0.82,
                    "max_vil_kg_m2": max_vil,
                    "severity": "SEVERE",
                    "hail_risk_pct": 80 if max_vil > 30 else 20,
                    "speed_kmh": 42.0,
                    "heading_deg": 65.0,
                },
            ],
        },
        "sounding": {
            "CAPE_J_kg": cape,
            "CIN_J_kg": -40,
            "Deep_Layer_Shear_0_6km_kts": shear,
            "Lifted_Index_C": -5.5,
            "K_Index": 38.0,
            "Total_Totals_Index": 49.0,
        },
        "forecast": [
            {"lead_time_min": 15, "max_dbz": max_dbz - 2, "max_vil": max_vil - 2, "total_flash_rate": flash_rate - 5},
            {"lead_time_min": 30, "max_dbz": max_dbz - 5, "max_vil": max_vil - 5, "total_flash_rate": flash_rate - 12},
        ],
        "lightning_jump": {
            "jump_detected": has_jump,
            "sigma_metric": sigma,
            "dfr_dt": 28.5 if has_jump else 1.2,
            "current_rate_fpm": flash_rate,
            "estimated_lead_time_min": 26,
            "status": "CRITICAL" if has_jump else "NORMAL",
        },
        "cap_bulletin": {"status": "Actual"},
    }


# ==============================================================================
# Test: Data Models
# ==============================================================================

class TestAlertModels(unittest.TestCase):
    """Test alert data model construction and serialization."""

    def test_risk_level_enum(self):
        self.assertEqual(RiskLevel.SEVERE.value, "SEVERE")
        self.assertIn(RiskLevel.NORMAL, RiskLevel)

    def test_alert_category_enum(self):
        self.assertEqual(AlertCategory.LIGHTNING_JUMP.value, "LIGHTNING_JUMP")
        self.assertEqual(len(AlertCategory), 6)

    def test_impact_sector_enum(self):
        self.assertEqual(ImpactSector.AVIATION.value, "AVIATION")
        self.assertEqual(len(ImpactSector), 4)

    def test_risk_color_map(self):
        self.assertIn(RiskLevel.SEVERE, RISK_COLOR_MAP)
        self.assertTrue(RISK_COLOR_MAP[RiskLevel.SEVERE].startswith("#"))

    def test_risk_component_to_dict(self):
        comp = RiskComponent(
            name="Radar Intensity",
            weight=0.28,
            raw_value=55.0,
            unit="dBZ",
            normalized_score=78.5,
            weighted_score=21.98,
            level=RiskLevel.HIGH,
            explanation="Reflectivity exceeds severe threshold.",
        )
        d = comp.to_dict()
        self.assertEqual(d["name"], "Radar Intensity")
        self.assertEqual(d["level"], "HIGH")
        self.assertIsInstance(d["weighted_score"], float)

    def test_risk_assessment_to_dict(self):
        assessment = RiskAssessment(
            overall_score=72.5,
            risk_level=RiskLevel.HIGH,
            color="#f97316",
            components=[],
            summary="Test summary",
            primary_driver="Radar Intensity",
            is_alert_triggered=True,
            confidence_score=0.85,
        )
        d = assessment.to_dict()
        self.assertEqual(d["overall_score"], 72.5)
        self.assertEqual(d["risk_level"], "HIGH")
        self.assertTrue(d["is_alert_triggered"])
        self.assertIn("disclaimer", d)

    def test_sector_impact_to_dict(self):
        impact = SectorImpact(
            sector=ImpactSector.AVIATION,
            severity=RiskLevel.HIGH,
            headline="Wind shear risk near airport",
            hazards=["Turbulence", "Lightning"],
            affected_assets=["MAA Airport"],
            onset_lead_time_min=15,
            duration_min=45,
        )
        d = impact.to_dict()
        self.assertEqual(d["sector"], "AVIATION")
        self.assertEqual(len(d["hazards"]), 2)

    def test_decision_support_action_to_dict(self):
        action = DecisionSupportAction(
            action_id="ACT-001",
            sector=ImpactSector.PUBLIC_SAFETY,
            priority="IMMEDIATE",
            action="Issue shelter-in-place advisory",
            lead_time_min=20,
            target_audience="District Emergency Operations Center",
        )
        d = action.to_dict()
        self.assertEqual(d["priority"], "IMMEDIATE")
        self.assertEqual(d["sector"], "PUBLIC_SAFETY")

    def test_alert_item_to_dict(self):
        now = datetime.now(timezone.utc)
        alert = AlertItem(
            alert_id="ALT-TEST-001",
            timestamp=now.isoformat(),
            station="Test Station",
            target_lat=13.08,
            target_lon=80.27,
            risk_level=RiskLevel.SEVERE,
            category=AlertCategory.LIGHTNING_JUMP,
            headline="Test Alert",
            description="Test description",
            trigger_reason="Testing",
            lead_time_min=25,
            valid_until=(now + timedelta(minutes=30)).isoformat(),
            impacts=[],
            actions=[],
            risk_assessment=RiskAssessment(
                overall_score=80.0,
                risk_level=RiskLevel.SEVERE,
                color="#ef4444",
                components=[],
                summary="Test",
                primary_driver="Test",
                is_alert_triggered=True,
                confidence_score=0.9,
            ),
        )
        d = alert.to_dict()
        self.assertEqual(d["alert_id"], "ALT-TEST-001")
        self.assertEqual(d["risk_level"], "SEVERE")
        self.assertEqual(d["category"], "LIGHTNING_JUMP")
        self.assertFalse(d["acknowledged"])
        self.assertIsNone(d["ack_timestamp"])


# ==============================================================================
# Test: Alert Store Lifecycle
# ==============================================================================

class TestAlertStore(unittest.TestCase):
    """Test AlertStore deduplication, acknowledgment, and expiration."""

    def setUp(self):
        self.store = AlertStore()

    def _make_alert(self, alert_id="ALT-001", station="Chennai DWR",
                    category=AlertCategory.LIGHTNING_JUMP,
                    risk_level=RiskLevel.HIGH, valid_minutes=30):
        now = datetime.now(timezone.utc)
        return AlertItem(
            alert_id=alert_id,
            timestamp=now.isoformat(),
            station=station,
            target_lat=13.08,
            target_lon=80.27,
            risk_level=risk_level,
            category=category,
            headline="Test",
            description="Test",
            trigger_reason="Test",
            lead_time_min=20,
            valid_until=(now + timedelta(minutes=valid_minutes)).isoformat(),
            impacts=[],
            actions=[],
            risk_assessment=RiskAssessment(
                overall_score=70.0,
                risk_level=risk_level,
                color="#f97316",
                components=[],
                summary="Test",
                primary_driver="Test",
                is_alert_triggered=True,
                confidence_score=0.8,
            ),
        )

    def test_add_alert_new(self):
        alert = self._make_alert()
        stored, is_new = self.store.add_alert(alert)
        self.assertTrue(is_new)
        self.assertEqual(stored.alert_id, "ALT-001")

    def test_get_active_alerts(self):
        self.store.add_alert(self._make_alert("A1"))
        self.store.add_alert(self._make_alert("A2", category=AlertCategory.SEVERE_CONVECTION))
        active = self.store.get_active_alerts()
        self.assertEqual(len(active), 2)

    def test_dedup_same_severity(self):
        """Same station + category + same/lower severity → no duplicate."""
        a1 = self._make_alert("A1", risk_level=RiskLevel.HIGH)
        a2 = self._make_alert("A2", risk_level=RiskLevel.HIGH)
        self.store.add_alert(a1)
        _, is_new = self.store.add_alert(a2)
        self.assertFalse(is_new)
        active = self.store.get_active_alerts()
        self.assertEqual(len(active), 1)

    def test_dedup_escalation(self):
        """Same station + category + higher severity → old retired, new added."""
        a1 = self._make_alert("A1", risk_level=RiskLevel.MODERATE)
        a2 = self._make_alert("A2", risk_level=RiskLevel.SEVERE)
        self.store.add_alert(a1)
        stored, is_new = self.store.add_alert(a2)
        self.assertTrue(is_new)
        active = self.store.get_active_alerts()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].risk_level, RiskLevel.SEVERE)

    def test_acknowledge_alert(self):
        alert = self._make_alert()
        self.store.add_alert(alert)
        result = self.store.acknowledge_alert("ALT-001")
        self.assertIsNotNone(result)
        self.assertTrue(result.acknowledged)
        self.assertIsNotNone(result.ack_timestamp)

    def test_acknowledge_nonexistent(self):
        result = self.store.acknowledge_alert("DOES-NOT-EXIST")
        self.assertIsNone(result)

    def test_get_alert_history(self):
        self.store.add_alert(self._make_alert("A1"))
        self.store.add_alert(self._make_alert("A2", category=AlertCategory.HAIL_HAZARD))
        history = self.store.get_alert_history(limit=10)
        self.assertEqual(len(history), 2)

    def test_get_stats(self):
        self.store.add_alert(self._make_alert("A1"))
        stats = self.store.get_stats()
        self.assertEqual(stats["active_count"], 1)
        self.assertIn("by_severity", stats)

    def test_clear(self):
        self.store.add_alert(self._make_alert())
        self.store.clear()
        self.assertEqual(len(self.store.get_active_alerts()), 0)

    def test_get_alert_by_id(self):
        alert = self._make_alert("A1")
        self.store.add_alert(alert)
        found = self.store.get_alert_by_id("A1")
        self.assertIsNotNone(found)
        self.assertEqual(found.alert_id, "A1")

    def test_get_alert_by_id_not_found(self):
        found = self.store.get_alert_by_id("NOPE")
        self.assertIsNone(found)


# ==============================================================================
# Test: Alert Rules / Risk Scoring
# ==============================================================================

class TestAlertRules(unittest.TestCase):
    """Test explainable risk scoring calculations."""

    def test_load_default_config(self):
        config = load_alert_config(None)
        self.assertIn("scoring_weights", config)
        weights = config["scoring_weights"]
        total = sum(weights.values())
        self.assertAlmostEqual(total, 1.0, places=2)

    def test_assess_convective_risk_severe(self):
        """High dBZ + jump + high CAPE → SEVERE or HIGH risk."""
        data = _make_nowcast(max_dbz=60.0, max_vil=45.0, flash_rate=80.0, has_jump=True, cape=3000, shear=30)
        config = load_alert_config(None)
        assessment = assess_convective_risk(data, config)
        self.assertIsInstance(assessment, RiskAssessment)
        self.assertIn(assessment.risk_level, [RiskLevel.HIGH, RiskLevel.SEVERE])
        self.assertTrue(assessment.is_alert_triggered)
        self.assertGreater(assessment.overall_score, 40.0)

    def test_assess_convective_risk_low(self):
        """Low dBZ, no jump, low CAPE → LOW or NORMAL."""
        data = _make_nowcast(max_dbz=15.0, max_vil=3.0, flash_rate=0.5, has_jump=False, cape=400, shear=5)
        config = load_alert_config(None)
        assessment = assess_convective_risk(data, config)
        self.assertIn(assessment.risk_level, [RiskLevel.NORMAL, RiskLevel.LOW])
        self.assertFalse(assessment.is_alert_triggered)

    def test_assess_components_present(self):
        """All five scoring components should be present."""
        data = _make_nowcast()
        config = load_alert_config(None)
        assessment = assess_convective_risk(data, config)
        self.assertEqual(len(assessment.components), 5)
        names = {c.name for c in assessment.components}
        self.assertIn("Radar Convective Intensity", names)
        self.assertIn("Lightning & Jump Precursor", names)

    def test_estimate_sector_impacts(self):
        data = _make_nowcast()
        config = load_alert_config(None)
        assessment = assess_convective_risk(data, config)
        impacts = estimate_sector_impacts(assessment, data, config)
        self.assertIsInstance(impacts, list)
        self.assertGreater(len(impacts), 0)
        sectors = {imp.sector for imp in impacts}
        self.assertTrue(sectors.issubset({ImpactSector.AVIATION, ImpactSector.POWER_GRID, ImpactSector.PUBLIC_SAFETY, ImpactSector.AGRICULTURE}))

    def test_generate_decision_support_actions(self):
        data = _make_nowcast()
        config = load_alert_config(None)
        assessment = assess_convective_risk(data, config)
        impacts = estimate_sector_impacts(assessment, data, config)
        actions = generate_decision_support_actions(assessment, impacts)
        self.assertIsInstance(actions, list)
        # With severe risk, there should be at least some actions
        if assessment.risk_level in [RiskLevel.HIGH, RiskLevel.SEVERE]:
            self.assertGreater(len(actions), 0)

    def test_haversine_km(self):
        # Chennai to Delhi rough distance ~1750 km
        dist = haversine_km(13.08, 80.27, 28.61, 77.21)
        self.assertGreater(dist, 1700)
        self.assertLess(dist, 1800)
        # Same point = 0
        self.assertAlmostEqual(haversine_km(13.08, 80.27, 13.08, 80.27), 0.0, places=1)


# ==============================================================================
# Test: Alert Engine End-to-End
# ==============================================================================

class TestAlertEngine(unittest.TestCase):
    """Test the full alert engine pipeline."""

    def setUp(self):
        self.engine = AlertEngine()

    def test_evaluate_nowcast_severe_with_jump(self):
        """Severe storm + lightning jump → assessment + at least 1 alert."""
        data = _make_nowcast(max_dbz=58.0, max_vil=44.0, flash_rate=76.0, has_jump=True, sigma=3.4)
        assessment, alerts = self.engine.evaluate_nowcast(data)
        self.assertIsInstance(assessment, RiskAssessment)
        self.assertGreater(len(alerts), 0)
        # At least a lightning jump alert
        categories = {a.category for a in alerts}
        self.assertIn(AlertCategory.LIGHTNING_JUMP, categories)

    def test_evaluate_nowcast_no_alerts_calm(self):
        """Calm conditions → no alerts triggered."""
        data = _make_nowcast(max_dbz=10.0, max_vil=2.0, flash_rate=0.2, has_jump=False, cape=200, shear=3)
        assessment, alerts = self.engine.evaluate_nowcast(data)
        self.assertIsInstance(assessment, RiskAssessment)
        self.assertEqual(len(alerts), 0)

    def test_evaluate_severe_convection_no_jump(self):
        """High dBZ but no lightning jump → severe convection alert."""
        data = _make_nowcast(max_dbz=55.0, max_vil=30.0, flash_rate=20.0, has_jump=False, cape=2000, shear=20)
        assessment, alerts = self.engine.evaluate_nowcast(data)
        if alerts:
            categories = {a.category for a in alerts}
            self.assertIn(AlertCategory.SEVERE_CONVECTION, categories)

    def test_last_assessment_stored(self):
        """The engine should cache the last assessment."""
        self.assertIsNone(self.engine.last_assessment)
        data = _make_nowcast()
        assessment, _ = self.engine.evaluate_nowcast(data)
        self.assertIsNotNone(self.engine.last_assessment)
        self.assertEqual(self.engine.last_assessment.overall_score, assessment.overall_score)

    def test_store_dedup_on_repeated_evaluation(self):
        """Repeated evaluations for same station should not spam alerts."""
        data = _make_nowcast(max_dbz=55.0, has_jump=True)
        self.engine.evaluate_nowcast(data)
        self.engine.evaluate_nowcast(data)
        active = self.engine.store.get_active_alerts()
        # Should not have duplicate categories for same station
        station_cats = [(a.station, a.category) for a in active]
        self.assertEqual(len(station_cats), len(set(station_cats)))

    def test_alert_to_dict_serializable(self):
        """All alerts should produce valid JSON-serializable dicts."""
        import json
        data = _make_nowcast(max_dbz=58.0, has_jump=True)
        _, alerts = self.engine.evaluate_nowcast(data)
        for alert in alerts:
            d = alert.to_dict()
            serialized = json.dumps(d)
            self.assertIsInstance(serialized, str)

    def test_risk_assessment_to_dict_serializable(self):
        """Risk assessment should serialize cleanly."""
        import json
        data = _make_nowcast()
        assessment, _ = self.engine.evaluate_nowcast(data)
        d = assessment.to_dict()
        serialized = json.dumps(d)
        self.assertIsInstance(serialized, str)
        parsed = json.loads(serialized)
        self.assertIn("overall_score", parsed)
        self.assertIn("components", parsed)


if __name__ == "__main__":
    unittest.main()

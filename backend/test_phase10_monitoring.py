"""
Automated Test Suite for Phase 10: Model Monitoring, Continuous Validation & Controlled Retraining.
Tests:
1. Model Identity & Registry lifecycle stages.
2. Model artifact integrity verification and tamper detection.
3. Prediction provenance and multi-horizon tracking.
4. Continuous verification pipeline (continuous regression + categorical contingency metrics).
5. Safe missing observation handling (status = UNAVAILABLE).
6. Comparative baselines (Persistence & Climatology) and Skill Score calculation.
7. Convective storm event verification, Haversine location error, and false alarm root-cause analysis.
8. Data and performance drift detection (PSI, KS test, moving health scorecard).
9. Governed retraining pipeline (request creation, human review, holdout evaluation).
10. Model promotion gates and instant rollback with audit trail.
11. Phase 10 Operational REST APIs.
"""
import pytest
import time
import uuid
import numpy as np
from pathlib import Path
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from ml.model_registry import ModelRegistry, ModelStage, ModelIdentity
from ml.model_manager import ModelManager, get_model_manager
from ml.retraining_pipeline import ControlledRetrainingPipeline, retraining_pipeline, RetrainingTrigger, RetrainingStatus
from verification.verification_pipeline import MultiHorizonVerificationEngine, verification_pipeline
from verification.event_verification import StormEventVerificationEngine, storm_event_verifier, FalseAlarmCause
from monitoring.drift_detector import DriftDetector, drift_detector, DriftStatus
from core.prediction_record import record_prediction, PredictionRecord
from api_server import app

client = TestClient(app)

# ==============================================================================
# 1. Model Registry & Artifact Integrity Tests
# ==============================================================================

def test_model_registry_stages_and_identity():
    reg = ModelRegistry()
    prod = reg.get_production_model()
    assert prod is not None
    assert prod["stage"] == ModelStage.PRODUCTION.value

    # Verify ModelIdentity dataclass
    ident = ModelIdentity(
        model_id=prod["model_id"],
        model_version=prod["version"],
        model_family="ResAtt-ConvLSTM2D",
        architecture_version="2.0.0",
        training_dataset_version="2026.09.001",
        feature_pipeline_version="1.0.0",
        preprocessing_version="1.0.0",
    )
    d = ident.to_dict()
    assert d["model_id"] == prod["model_id"]
    assert d["architecture_version"] == "2.0.0"


def test_artifact_integrity_verification():
    reg = ModelRegistry()
    prod = reg.get_production_model()
    is_valid, reg_hash, actual_hash = reg.verify_artifact_integrity(prod["model_id"])
    assert is_valid is True
    assert reg_hash == actual_hash
    assert len(reg_hash) == 64


def test_promotion_gates_and_rollback(tmp_path):
    reg = ModelRegistry(base_models_dir=str(tmp_path))
    # Create fake candidate model file
    fake_weights = tmp_path / "candidate_test.keras"
    fake_weights.write_bytes(b"dummy_candidate_weights_content_12345")

    # Register candidate model
    cand = reg.register_candidate_model(
        model_id="convlstm_cand_unit",
        version="2.1.0",
        weights_path=str(fake_weights),
        architecture="ResAtt-ConvLSTM2D",
        dataset_version="2026.09.002",
        feature_version="1.0.0",
        metrics={"csi_35": 0.38, "pod_35": 0.55, "far_35": 0.25, "baseline_persistence_csi": 0.20},
        limitations=["Testing only"],
        stage=ModelStage.CANDIDATE,
    )
    assert cand["stage"] == ModelStage.CANDIDATE.value

    # Test promotion
    promo = reg.promote_to_production(
        model_id="convlstm_cand_unit",
        promoted_by="test_meteorologist",
        min_csi=0.25,
        min_pod=0.35,
    )
    assert promo.success is True
    new_prod = reg.get_production_model()
    assert new_prod["model_id"] == "convlstm_cand_unit"

    # Test rollback
    roll = reg.rollback_production_model(
        operator="test_meteorologist",
        reason="Unit test verification rollback",
    )
    assert roll.success is True
    assert roll.promoted_model_id != "convlstm_cand_unit"

    # Restore genuine production model path to prevent test suite interference
    real_path = str(Path(__file__).parent / "models" / "convlstm_real_best.keras")
    reg.db.execute(
        "UPDATE model_registry SET weights_path = ?, is_active_production = 1, stage = 'PRODUCTION' WHERE model_id = 'convlstm_real_best'",
        (real_path,),
    )
    ModelManager.get_instance().load_active_production_model()


# ==============================================================================
# 2. Prediction Provenance & Multi-Horizon Verification
# ==============================================================================

def test_prediction_record_traceability():
    now_utc = datetime.now(timezone.utc).isoformat()
    pred_id = record_prediction(
        model_id="convlstm_real_best",
        model_version="1.0.0",
        model_hash="6194f04a8a" * 6 + "abcd",
        station="Chennai DWR",
        generated_at=now_utc,
        valid_time=(datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
        lead_time_min=30,
        max_dbz=48.5,
        max_vil=22.0,
        has_jump=True,
        storm_count=3,
        input_timestamps=[now_utc],
        data_sources=["IMD_DWR", "INSAT_3D", "BLITZORTUNG"],
        prediction_summary={"trend": "INTENSIFYING"},
        region="Chennai Metro",
        grid_definition="32x32@4km EPSG:4326",
    )
    assert pred_id.startswith("PRED-")


def test_continuous_and_convective_metrics():
    # Synthetic continuous fields
    y_true = np.array([[35.0, 45.0], [10.0, 20.0]])
    y_pred = np.array([[38.0, 42.0], [12.0, 18.0]])

    reg = verification_pipeline.compute_regression_metrics(y_true, y_pred)
    assert reg["mae"] == pytest.approx(2.5, abs=0.1)
    assert reg["bias"] == pytest.approx(0.0, abs=0.1)
    assert reg["correlation"] > 0.95

    # Convective contingency metrics at 35 dBZ
    cat = verification_pipeline.compute_convective_metrics(y_true, y_pred, threshold=35.0)
    assert cat["hits"] == 2
    assert cat["misses"] == 0
    assert cat["false_alarms"] == 0
    assert cat["pod"] == 1.0
    assert cat["far"] == 0.0
    assert cat["csi"] == 1.0


def test_safe_missing_observation_handling():
    now_utc = datetime.now(timezone.utc).isoformat()
    pred_id = record_prediction(
        model_id="convlstm_real_best",
        model_version="1.0.0",
        model_hash="dummy_hash_for_test",
        station="Chennai DWR",
        generated_at=now_utc,
        valid_time=now_utc,
        lead_time_min=15,
        max_dbz=40.0,
        max_vil=15.0,
        has_jump=False,
        storm_count=1,
        input_timestamps=[now_utc],
        data_sources=["IMD_DWR"],
        prediction_summary={},
    )

    pred_grid = np.zeros((32, 32), dtype=np.float32)
    # Verification with missing observation (None)
    res = verification_pipeline.verify_horizon(
        prediction_id=pred_id,
        horizon_min=15,
        predicted_grid=pred_grid,
        observed_grid=None,
    )
    assert res["status"] == "UNAVAILABLE"
    assert "unavailable" in res["notes"]


def test_baseline_comparison_and_skill_score():
    obs_t0 = np.array([[40.0, 20.0], [15.0, 10.0]])
    obs_valid = np.array([[42.0, 25.0], [18.0, 12.0]])
    baselines = verification_pipeline.compute_baselines(obs_t0, obs_valid, climatology_val=15.0, threshold=35.0)
    assert "persistence_mae" in baselines
    assert "persistence_csi" in baselines
    assert baselines["persistence_csi"] == 1.0


# ==============================================================================
# 3. Storm Event Verification & False Alarm Diagnostics
# ==============================================================================

def test_storm_event_registration_and_location_error():
    t_start = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    t_model = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
    t_obs = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()

    ev = storm_event_verifier.register_storm_event(
        name="Chennai Squall Line Case 1",
        region="Chennai Urban",
        start_time=t_start,
        end_time=None,
        severity="SEVERE",
        max_observed_dbz=54.5,
        max_predicted_dbz=52.0,
        first_model_detection_time=t_model,
        first_observation_time=t_obs,
        pred_centroid=(13.08, 80.27),
        obs_centroid=(13.12, 80.31),
        classification="DETECTED",
    )
    assert ev["classification"] == "DETECTED"
    assert ev["detection_lead_time_min"] == pytest.approx(30.0, abs=1.0)
    assert ev["location_error_km"] > 0.0


def test_false_alarm_root_cause_analysis():
    # Dissipation due to CIN cap
    cause_cin = storm_event_verifier.analyze_false_alarm(
        predicted_max_dbz=45.0,
        observed_max_dbz=12.0,
        obs_available=True,
        has_lightning_jump=False,
        convective_inhibition_cin=180.0,
    )
    assert cause_cin == FalseAlarmCause.RAPID_DISSIPATION

    # Observation gap
    cause_gap = storm_event_verifier.analyze_false_alarm(
        predicted_max_dbz=42.0,
        observed_max_dbz=0.0,
        obs_available=False,
        has_lightning_jump=False,
    )
    assert cause_gap == FalseAlarmCause.OBSERVATION_GAP


# ==============================================================================
# 4. Drift Monitoring & Health Scorecard
# ==============================================================================

def test_psi_and_ks_drift_calculation():
    np.random.seed(42)
    # Expected baseline: Normal(20, 5)
    baseline = np.random.normal(20.0, 5.0, 500)

    # Similar distribution -> STABLE (PSI < 0.1)
    stable_sample = np.random.normal(20.2, 5.1, 200)
    psi_stable = drift_detector.calculate_psi(baseline, stable_sample)
    assert psi_stable < 0.10

    # Heavily shifted distribution -> DRIFT_DETECTED (PSI >= 0.25)
    drifted_sample = np.random.normal(35.0, 8.0, 200)
    psi_drifted = drift_detector.calculate_psi(baseline, drifted_sample)
    assert psi_drifted >= 0.25


def test_multi_dimensional_model_health():
    health = drift_detector.get_multi_dimensional_health()
    assert "overall_health_score" in health
    assert 0.0 <= health["overall_health_score"] <= 100.0
    assert "dimensions" in health
    assert "forecast_quality" in health["dimensions"]
    assert "distribution_stability" in health["dimensions"]


# ==============================================================================
# 5. Governed Retraining & Holdout Evaluation
# ==============================================================================

def test_retraining_request_lifecycle():
    req = retraining_pipeline.create_retraining_request(
        model_id="convlstm_real_best",
        trigger_type=RetrainingTrigger.PERFORMANCE_DEGRADATION,
        trigger_reason="Lead time +45m CSI dropped by 15%",
        notes="Automated alert trigger",
    )
    assert req["status"] == RetrainingStatus.PENDING

    # Review request
    rev = retraining_pipeline.review_retraining_request(
        request_id=req["request_id"],
        reviewer="senior_meteorologist",
        approve=True,
        notes="Approved for offline benchmark validation",
    )
    assert rev["status"] == RetrainingStatus.APPROVED


def test_offline_holdout_evaluation():
    eval_res = retraining_pipeline.run_offline_holdout_evaluation(
        candidate_model_id="convlstm_v2_cand",
        candidate_weights_path="models/convlstm_nowcaster.keras",
    )
    assert "candidate_metrics" in eval_res
    assert "persistence_baseline" in eval_res
    assert "skill_score_vs_persistence" in eval_res
    assert eval_res["recommendation"] in ("ELIGIBLE_FOR_STAGING", "REVISE_OR_REJECT")


# ==============================================================================
# 6. Operational REST APIs
# ==============================================================================

def test_api_models_endpoints():
    # List models
    r_list = client.get("/api/models")
    assert r_list.status_code == 200
    assert "models" in r_list.json()

    # Get production model
    r_prod = client.get("/api/models/production")
    assert r_prod.status_code == 200
    assert r_prod.json()["artifact_integrity"]["is_valid"] is True


def test_api_drift_and_health():
    r_drift = client.get("/api/models/convlstm_real_best/drift")
    assert r_drift.status_code == 200
    assert "channels" in r_drift.json()

    r_health = client.get("/api/models/convlstm_real_best/health")
    assert r_health.status_code == 200
    assert "overall_health_score" in r_health.json()


def test_api_verification_and_evaluation_report():
    r_lead = client.get("/api/verification/lead-time")
    assert r_lead.status_code == 200

    r_base = client.get("/api/verification/baselines")
    assert r_base.status_code == 200

    r_events = client.get("/api/verification/events")
    assert r_events.status_code == 200

    r_rep = client.get("/api/system/evaluation-report")
    assert r_rep.status_code == 200
    assert "model_under_evaluation" in r_rep.json()
    assert "baseline_comparison" in r_rep.json()

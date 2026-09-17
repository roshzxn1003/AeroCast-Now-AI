"""
Automated Test Suite for Phase 9: Operational Data Infrastructure & Multi-Source Ingestion.
Validates:
1. Canonical Observation schemas, types, and cryptographic checksums.
2. Provider adapters (Radar, Satellite, Lightning, NWP).
3. Circuit breaker state machine and bounded backoff.
4. Primary -> Secondary failover and recovery.
5. Raw data preservation and idempotent deduplication.
6. Temporal synchronization, missingness, and forward-fill tagging.
7. Geospatial regridding and peak-preserving interpolation.
8. Historical replay engine lifecycle.
9. Inference readiness gate safety rules.
10. Operational Data REST APIs.
"""
import pytest
import time
import uuid
import numpy as np
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from core.canonical_observation import (
    ObservationType,
    CanonicalQualityFlag,
    CanonicalProvenance,
    ProcessingStatus,
    SpatialDomain,
    ScalarObservation,
    GriddedObservation,
    TimeSeriesObservation,
)
from ingestion.circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerConfig
from ingestion.adapters.radar_adapter import IMDDopplerRadarAdapter, RainViewerRadarAdapter
from ingestion.adapters.satellite_adapter import INSATSatelliteAdapter, OpenMeteoCloudAdapter
from ingestion.adapters.lightning_adapter import BlitzortungLightningAdapter, LightningArchiveAdapter
from ingestion.adapters.nwp_adapter import OpenMeteoNWPAdapter, ClimatologySoundingAdapter
from ingestion.provider_manager import ProviderManager, provider_manager
from ingestion.raw_storage import RawDataStorage, raw_storage
from ingestion.temporal_sync import TemporalSynchronizer, SynchronizedTemporalSequence, temporal_synchronizer
from ingestion.geospatial_regridder import GeospatialRegridder, regridder
from ingestion.inference_gate import InferenceReadinessGate, ReadinessStatus, inference_gate
from ingestion.replay_engine import HistoricalReplayEngine, replay_engine
from api_server import app

client = TestClient(app)

# ==============================================================================
# 1. Canonical Observation Tests
# ==============================================================================

def test_canonical_scalar_observation():
    now_utc = datetime.now(timezone.utc).isoformat()
    obs = ScalarObservation(
        observation_id=f"OBS-TEST-{uuid.uuid4().hex[:6]}",
        obs_type=None,
        source="TEST_SRC",
        provider="TEST_PROV",
        dataset="test_scalar",
        variable="temperature",
        timestamp=now_utc,
        valid_time=now_utc,
        ingestion_time=now_utc,
        unit="°C",
        quality_flag=CanonicalQualityFlag.VALID,
        latitude=13.0827,
        longitude=80.2707,
        value=31.5,
    )
    assert obs.obs_type == ObservationType.SCALAR
    assert obs.value == 31.5
    assert len(obs.checksum) == 64  # SHA-256 hex string


def test_canonical_gridded_observation():
    now_utc = datetime.now(timezone.utc).isoformat()
    grid = np.zeros((32, 32), dtype=np.float32)
    grid[10, 10] = 52.0

    obs = GriddedObservation(
        observation_id=f"OBS-GRID-{uuid.uuid4().hex[:6]}",
        obs_type=None,
        source="IMD",
        provider="IMD_DWR",
        dataset="radar_dbz",
        variable="reflectivity",
        timestamp=now_utc,
        valid_time=now_utc,
        ingestion_time=now_utc,
        unit="dBZ",
        grid_shape=(32, 32),
        grid_data=grid,
    )
    assert obs.obs_type == ObservationType.GRIDDED
    assert obs.max_value == 52.0
    assert obs.min_value == 0.0
    assert len(obs.checksum) == 64


# ==============================================================================
# 2. Circuit Breaker Tests
# ==============================================================================

def test_circuit_breaker_transitions():
    cfg = CircuitBreakerConfig(failure_threshold=2, cooldown_seconds=0.5)
    cb = CircuitBreaker("TEST_CB", cfg)
    assert cb.state == CircuitState.HEALTHY
    assert cb.can_execute() is True

    # First failure -> DEGRADED
    cb.record_failure("Error 1")
    assert cb.state == CircuitState.DEGRADED
    assert cb.can_execute() is True

    # Second failure -> OPEN
    cb.record_failure("Error 2")
    assert cb.state == CircuitState.OPEN
    assert cb.can_execute() is False

    # Wait for cooldown
    time.sleep(0.6)
    assert cb.can_execute() is True
    assert cb.state == CircuitState.HALF_OPEN

    # Recovery
    cb.record_success(15.0)
    assert cb.state == CircuitState.HEALTHY


# ==============================================================================
# 3. Provider Redundancy & Failover
# ==============================================================================

@pytest.mark.asyncio
async def test_provider_manager_failover():
    # Force primary circuit open
    cb = provider_manager._domains["RADAR"].primary.circuit_breaker
    cb.state = CircuitState.OPEN
    cb.last_trip_time = time.time()

    obs_list, meta = await provider_manager.fetch_domain("RADAR", 13.0827, 80.2707)
    assert meta["status"] == "SUCCESS_FALLBACK"
    assert meta["is_fallback"] is True
    assert meta["provider_selected"] == "RAINVIEWER_RADAR"
    assert len(obs_list) == 2

    # Restore primary
    cb.state = CircuitState.HEALTHY
    obs_list2, meta2 = await provider_manager.fetch_domain("RADAR", 13.0827, 80.2707)
    assert meta2["status"] == "SUCCESS"
    assert meta2["is_fallback"] is False
    assert meta2["provider_selected"] == "IMD_DWR"


# ==============================================================================
# 4. Raw Storage & Deduplication
# ==============================================================================

def test_raw_storage_deduplication(tmp_path):
    storage = RawDataStorage(base_dir=tmp_path)
    payload = {"station": "Chennai", "radar_dbz_max": 48.5, "unique_token": uuid.uuid4().hex}

    res1 = storage.store_raw_payload("RADAR", "TEST_P", "dwr", payload)
    assert res1["status"] == "STORED"
    assert res1["is_duplicate"] is False

    # Re-storing identical payload
    res2 = storage.store_raw_payload("RADAR", "TEST_P", "dwr", payload)
    assert res2["status"] == "DUPLICATE"
    assert res2["is_duplicate"] is True
    assert res1["file_hash"] == res2["file_hash"]


# ==============================================================================
# 5. Temporal Synchronization & Forward Fill
# ==============================================================================

def test_temporal_synchronization():
    now = datetime.now(timezone.utc)
    t_sync = TemporalSynchronizer()

    # Create observation at T-45
    t_45 = (now - timedelta(minutes=45)).isoformat()
    grid = np.full((32, 32), 35.0, dtype=np.float32)
    obs_dbz = GriddedObservation(
        observation_id=f"OBS-T45-{uuid.uuid4().hex[:6]}",
        obs_type=None,
        source="IMD",
        provider="IMD_DWR",
        dataset="dwr",
        variable="reflectivity",
        timestamp=t_45,
        valid_time=t_45,
        ingestion_time=t_45,
        unit="dBZ",
        grid_shape=(32, 32),
        grid_data=grid,
    )

    seq = t_sync.synchronize_observations([obs_dbz], t0=now)
    # T-45 slot (index 0) has genuine observation
    assert "reflectivity" in seq.slots[0].observations
    assert seq.slots[0].is_imputed["reflectivity"] is False

    # Forward fill propagates to T-30 (index 1) within 30m window
    assert "reflectivity" in seq.slots[1].observations
    assert seq.slots[1].is_imputed["reflectivity"] is True

    # Assemble tensor
    tensor, meta = t_sync.assemble_tensor_frames(seq)
    assert tensor.shape == (1, 4, 32, 32, 4)
    assert not np.isnan(tensor).any()


# ==============================================================================
# 6. Geospatial Harmonization
# ==============================================================================

def test_geospatial_regridder_preserve_peak():
    rg = GeospatialRegridder()
    # 64x64 grid with sharp convective peak
    high_res = np.zeros((64, 64), dtype=np.float32)
    high_res[32, 32] = 68.5  # Severe hail core

    low_res = rg.resize_grid(high_res, (32, 32), preserve_max=True)
    assert low_res.shape == (32, 32)
    # Peak must be preserved
    assert np.max(low_res) == pytest.approx(68.5, abs=0.1)


# ==============================================================================
# 7. Inference Readiness Gate
# ==============================================================================

def test_inference_readiness_gate():
    gate = InferenceReadinessGate()
    seq = SynchronizedTemporalSequence()

    # Empty sequence -> Degraded with warnings
    res = gate.evaluate_readiness(seq)
    assert res.is_ready is True
    assert res.status in (ReadinessStatus.DEGRADED, ReadinessStatus.BLOCKED)

    # Corrupted tensor with NaN -> BLOCKED
    t0_slot = seq.slots[3]
    nan_grid = np.full((32, 32), np.nan, dtype=np.float32)
    bad_obs = GriddedObservation(
        observation_id="BAD-OBS",
        obs_type=None,
        source="IMD",
        provider="IMD_DWR",
        dataset="dwr",
        variable="reflectivity",
        timestamp=datetime.now(timezone.utc).isoformat(),
        valid_time=datetime.now(timezone.utc).isoformat(),
        ingestion_time=datetime.now(timezone.utc).isoformat(),
        unit="dBZ",
        grid_shape=(32, 32),
        grid_data=nan_grid,
    )
    t0_slot.observations["reflectivity"] = bad_obs
    res_bad = gate.evaluate_readiness(seq)
    assert res_bad.status == ReadinessStatus.BLOCKED
    assert res_bad.is_ready is False
    assert any("NaN" in reason for reason in res_bad.blocking_reasons)


# ==============================================================================
# 8. Historical Replay Engine Lifecycle
# ==============================================================================

@pytest.mark.asyncio
async def test_replay_engine_lifecycle():
    now = datetime.now(timezone.utc)
    t_start = (now - timedelta(hours=1)).isoformat()
    t_end = now.isoformat()

    start_res = await replay_engine.start_replay(t_start, t_end, speed_multiplier=10.0, step_minutes=15)
    assert start_res["status"] == "STARTED"
    assert replay_engine.get_status()["is_active"] is True
    assert provider_manager.operational_mode == "REPLAY"

    step_res = await replay_engine.step_replay()
    assert step_res is not None
    assert step_res["step_index"] == 0

    stop_res = replay_engine.stop_replay()
    assert stop_res["status"] == "STOPPED"
    assert provider_manager.operational_mode == "REAL"


# ==============================================================================
# 9. Operational REST APIs
# ==============================================================================

def test_api_data_sources():
    resp = client.get("/data/sources")
    assert resp.status_code == 200
    data = resp.json()
    assert "providers" in data
    assert len(data["providers"]) >= 8  # 4 domains * 2 providers


def test_api_data_health():
    resp = client.get("/data/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("HEALTHY", "DEGRADED")
    assert "domains" in data
    assert "RADAR" in data["domains"]


def test_api_data_freshness():
    resp = client.get("/data/freshness")
    assert resp.status_code == 200
    data = resp.json()
    assert "channels" in data


def test_api_data_coverage():
    resp = client.get("/data/coverage")
    assert resp.status_code == 200
    data = resp.json()
    assert data["canonical_grid"]["total_cells"] == 1024
    assert data["canonical_grid"]["cell_resolution_km"] == 4.0


def test_api_data_gate():
    resp = client.get("/data/gate")
    assert resp.status_code == 200
    data = resp.json()
    assert "is_ready" in data
    assert "status" in data


def test_api_data_replay():
    resp = client.get("/data/replay")
    assert resp.status_code == 200
    data = resp.json()
    assert "is_active" in data

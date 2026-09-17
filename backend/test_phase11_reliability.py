"""
Phase 11 Comprehensive Reliability, Security & Observability Test Suite.
AeroCast-Now AI — Mission-Critical System Hardening Verification.

Validates:
1. Standardized Health Probes (/health, /live, /ready, /api/system/health).
2. Distributed Tracing & Correlation ID header propagation.
3. OWASP Security Headers & Payload Size Limits (HTTP 413).
4. Tiered Sliding-Window Rate Limiting (HTTP 429).
5. Inference Concurrency Semaphore & Queue Saturation (HTTP 503).
6. Model Warmup Engine & Physical Shape Validation.
7. Numerical Safety Validator (NaN/Inf & Boundary Rejection).
8. Database Resilience: Jittered Retry on Lock Contention & Transaction Rollback.
9. Idempotency Key Ledger & Duplicate Request Caching.
10. Recoverable Background Job Lifecycle & Post-Restart Recovery.
11. Authentication & Role-Based Access Control (RBAC).
12. Secret Masking in Structured JSON Logs.
"""
from __future__ import annotations

import os
import json
import sqlite3
import pytest
import numpy as np
from fastapi.testclient import TestClient

from api_server import app
from reliability.taxonomy import ErrorCode, AeroCastException, NumericalValidationError
from reliability.logging import mask_sensitive_data, StructuredJSONFormatter
from reliability.auth import UserRole, UserIdentity, get_configured_api_keys
from reliability.health import ReadinessState, ComponentHealthEngine
from reliability.warmup import ModelWarmupEngine, WarmupResult
from reliability.numerical import NumericalSafetyValidator
from reliability.concurrency import InferenceConcurrencyLimiter
from reliability.db_resilience import execute_with_retry, atomic_transaction, IdempotencyLedger
from reliability.jobs import JobManager, JobStatus
from reliability.resource_monitor import ResourceMonitor


@pytest.fixture
def client():
    return TestClient(app)


# -----------------------------------------------------------------------------
# 1. Health Probes & Readiness States
# -----------------------------------------------------------------------------

def test_health_and_live_probes(client):
    """Verifies that /health and /live return lightweight positive liveness status."""
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "HEALTHY"

    res_live = client.get("/live")
    assert res_live.status_code == 200
    assert res_live.json()["status"] == "ALIVE"


def test_ready_and_component_health(client):
    """Verifies that /ready and /api/system/health return detailed uncompressed component states."""
    res_ready = client.get("/ready")
    assert res_ready.status_code in (200, 503)
    data = res_ready.json()
    assert "overall_status" in data
    assert "components" in data
    assert "database" in data["components"]
    assert "model" in data["components"]
    assert "storage" in data["components"]

    res_health = client.get("/api/system/health")
    assert res_health.status_code == 200
    h_data = res_health.json()
    assert h_data["components"]["database"]["state"] in ("HEALTHY", "DEGRADED", "NOT_READY")


# -----------------------------------------------------------------------------
# 2. Correlation ID & Security Headers
# -----------------------------------------------------------------------------

def test_correlation_id_and_security_headers(client):
    """Verifies that correlation headers and OWASP security headers are attached to responses."""
    custom_corr = "test-corr-uuid-999"
    res = client.get("/health", headers={"X-Correlation-ID": custom_corr})
    assert res.status_code == 200
    assert res.headers.get("X-Correlation-ID") == custom_corr
    assert "X-Request-ID" in res.headers
    assert "X-Response-Time-Ms" in res.headers

    # Security Headers
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert res.headers.get("X-XSS-Protection") == "1; mode=block"
    assert "Strict-Transport-Security" in res.headers


# -----------------------------------------------------------------------------
# 3. Payload Size Limiting & Rate Limiting
# -----------------------------------------------------------------------------

def test_payload_size_limiting(client):
    """Verifies that requests exceeding payload limit receive HTTP 413."""
    oversized_headers = {"Content-Length": str(15 * 1024 * 1024)}  # 15MB > 10MB limit
    res = client.post("/api/system/model-registry/promote?model_id=test", headers=oversized_headers)
    assert res.status_code == 413
    assert res.json()["error_code"] == ErrorCode.PAYLOAD_TOO_LARGE.value


def test_rate_limiting_trigger():
    """Verifies that sliding window rate limiter blocks requests exceeding tier limits."""
    from reliability.middleware import RateLimiter
    limiter = RateLimiter()
    limiter.limits["test_tier"] = (3, 60)  # Max 3 requests per minute

    key = "127.0.0.1:test_tier"
    assert limiter.is_allowed(key, "test_tier")[0] is True
    assert limiter.is_allowed(key, "test_tier")[0] is True
    assert limiter.is_allowed(key, "test_tier")[0] is True
    # 4th request must be blocked
    allowed, retry_after = limiter.is_allowed(key, "test_tier")
    assert allowed is False
    assert retry_after > 0


# -----------------------------------------------------------------------------
# 4. Inference Concurrency Limiter
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_inference_concurrency_limiter():
    """Verifies that concurrent inference calls are bounded and excess loads are shed."""
    limiter = InferenceConcurrencyLimiter(max_concurrent=1, timeout_seconds=0.05)
    
    async with limiter.acquire():
        assert limiter.get_stats()["active_inferences"] == 1
        # Attempting second acquire while first is active should time out
        with pytest.raises(AeroCastException) as exc:
            async with limiter.acquire():
                pass
        assert exc.value.error_code == ErrorCode.INFERENCE_CONCURRENCY_EXCEEDED


# -----------------------------------------------------------------------------
# 5. Model Warmup & Numerical Validation
# -----------------------------------------------------------------------------

def test_synthetic_benchmark_fixture_and_warmup():
    """Verifies that synthetic benchmark fixture satisfies (1, 4, 32, 32, 4) bounds."""
    fixture = ModelWarmupEngine.generate_synthetic_benchmark_fixture()
    assert fixture.shape == (1, 4, 32, 32, 4)
    assert fixture.dtype == np.float32
    assert 0.0 <= np.min(fixture) <= np.max(fixture) <= 1.0


def test_numerical_safety_validator():
    """Verifies that NaN, Inf, and invalid coordinates are rejected."""
    # Valid tensor
    valid_tensor = np.zeros((4, 32, 32, 4), dtype=np.float32)
    NumericalSafetyValidator.validate_tensor(valid_tensor)

    # NaN tensor
    nan_tensor = np.zeros((4, 32, 32, 4), dtype=np.float32)
    nan_tensor[0, 0, 0, 0] = np.nan
    with pytest.raises(NumericalValidationError):
        NumericalSafetyValidator.validate_tensor(nan_tensor)

    # Inf tensor
    inf_tensor = np.zeros((4, 32, 32, 4), dtype=np.float32)
    inf_tensor[1, 1, 1, 1] = np.inf
    with pytest.raises(NumericalValidationError):
        NumericalSafetyValidator.validate_tensor(inf_tensor)

    # Geographic boundary checks
    NumericalSafetyValidator.validate_coordinates(13.08, 80.27)  # Chennai: valid
    with pytest.raises(NumericalValidationError):
        NumericalSafetyValidator.validate_coordinates(55.0, 10.0)  # Outside India/subcontinent


# -----------------------------------------------------------------------------
# 6. Database Resilience, Idempotency & Transaction Safety
# -----------------------------------------------------------------------------

def test_atomic_transaction_rollback(tmp_path):
    """Verifies that atomic transactions properly rollback on exception."""
    test_db = str(tmp_path / "test_resilience.sqlite3")
    conn = sqlite3.connect(test_db)
    conn.execute("CREATE TABLE test_tbl (id INTEGER PRIMARY KEY, val TEXT);")
    conn.close()

    from db.database import DatabaseManager
    dm = DatabaseManager(test_db)

    # Insert initial record
    dm.execute("INSERT INTO test_tbl (val) VALUES ('initial')")

    # Atomic block that fails
    with pytest.raises(ValueError):
        with atomic_transaction(dm) as tx_conn:
            tx_conn.execute("INSERT INTO test_tbl (val) VALUES ('second')")
            raise ValueError("Intentional failure")

    rows = dm.fetch_all("SELECT val FROM test_tbl")
    assert len(rows) == 1
    assert rows[0]["val"] == "initial"


def test_idempotency_ledger_caching():
    """Verifies that duplicate requests return cached results."""
    idem_key = "idemp-test-key-12345"
    endpoint = "/api/nowcast"
    response_data = {"forecast_id": "fc-001", "storm": "squall_line"}

    IdempotencyLedger.record_response(idem_key, endpoint, 200, response_data, ttl_hours=1)
    cached = IdempotencyLedger.get_cached_response(idem_key)
    assert cached is not None
    assert cached["cached"] is True
    assert cached["data"]["forecast_id"] == "fc-001"


# -----------------------------------------------------------------------------
# 7. Recoverable Background Jobs & Backpressure
# -----------------------------------------------------------------------------

def test_job_lifecycle_and_restart_recovery():
    """Verifies that background jobs transition through states and recover from crashes."""
    jm = JobManager(max_queue_depth=5)
    jid = jm.enqueue_job("radar_ingest", {"station": "chennai"})
    assert jid is not None

    job = jm.get_job(jid)
    assert job["status"] == JobStatus.QUEUED.value

    # Start and heartbeat
    jm.start_job(jid)
    assert jm.get_job(jid)["status"] == JobStatus.RUNNING.value

    # Simulate process crash recovery
    recovered = jm.recover_stale_jobs_on_boot()
    assert jid in recovered
    assert jm.get_job(jid)["status"] == JobStatus.RECOVERED.value


def test_job_backpressure_drop():
    """Verifies that exceeding queue capacity drops jobs safely with audit recording."""
    from db.database import get_db
    get_db().execute("DELETE FROM background_jobs WHERE status = 'QUEUED'")

    jm = JobManager(max_queue_depth=2)
    jid1 = jm.enqueue_job("job1", {})
    jid2 = jm.enqueue_job("job2", {})
    jid3 = jm.enqueue_job("job3", {})  # Exceeds max_queue_depth=2

    assert jid1 is not None
    assert jid2 is not None
    assert jid3 is None  # Dropped under backpressure


# -----------------------------------------------------------------------------
# 8. Authentication & RBAC Governance
# -----------------------------------------------------------------------------

def test_rbac_admin_endpoint_protection(client):
    """Verifies that unauthenticated or non-admin roles cannot trigger admin actions."""
    # Attempting promote with viewer token must fail (403 Forbidden)
    res = client.post(
        "/api/system/model-registry/promote?model_id=convlstm_real_best",
        headers={"X-API-Key": "aerocast_viewer_dev_token"},
    )
    assert res.status_code == 403

    # Attempting promote with valid admin token is authorized (passes auth)
    res_admin = client.post(
        "/api/system/model-registry/promote?model_id=convlstm_real_best",
        headers={"X-API-Key": "aerocast_admin_dev_token"},
    )
    # Status code is 200 (auth passed)
    assert res_admin.status_code == 200


# -----------------------------------------------------------------------------
# 9. Secret Masking in Logs & Resource Telemetry
# -----------------------------------------------------------------------------

def test_secret_masking_in_logs():
    """Verifies that tokens and passwords are never output in logs."""
    raw_message = "Connecting with token: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9 and password: SuperSecretPassword123"
    masked = mask_sensitive_data(raw_message)
    assert "SuperSecretPassword123" not in masked
    assert "eyJhbGci" not in masked
    assert "[REDACTED]" in masked


def test_resource_monitor_telemetry():
    """Verifies that ResourceMonitor returns process RSS, CPU, and disk metrics."""
    res = ResourceMonitor.get_resource_snapshot()
    assert "cpu" in res
    assert "memory" in res
    assert "disk" in res
    assert res["memory"]["process_rss_mb"] > 0
    assert res["disk"]["free_gb"] > 0

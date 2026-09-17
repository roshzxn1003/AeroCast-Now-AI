"""
Phase 12 Comprehensive Deployment, Scaling, Containerization & DR Test Suite.
AeroCast-Now AI — Production Readiness Verification.

Validates:
1. Multi-Environment Configuration Resolution & Hierarchy.
2. Fail-Fast Safety Invariants (Rejection of Insecure Secrets & Cross-Env Contamination).
3. Database Migration Engine (Versioning, Backup Snapshots, Rollback & Re-application).
4. Containerization Artifacts (Backend & Frontend Dockerfiles, Nginx Reverse Proxy, Compose).
5. Deployment Health Gate, Release Manifest, and Provenance Ledger.
6. Disaster Recovery & Scaling Benchmark Parity.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
from pathlib import Path
import pytest

from config.deployment_config import (
    DeploymentConfig,
    EnvironmentType,
    ConfigurationError,
    INSECURE_TEST_TOKENS,
)
from db.migrations import MigrationManager, MIGRATIONS


# -----------------------------------------------------------------------------
# 1. Multi-Environment Configuration Resolution & Isolation
# -----------------------------------------------------------------------------

def test_deployment_config_defaults(monkeypatch, tmp_path):
    """Verifies default environment resolution falls back safely to development."""
    monkeypatch.delenv("AEROCAST_ENV", raising=False)
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.setenv("AEROCAST_DATA_DIR", str(tmp_path))

    cfg = DeploymentConfig.from_env()
    assert cfg.env == EnvironmentType.DEVELOPMENT
    assert cfg.port == 8000
    assert cfg.data_mode == "hybrid"
    assert "aerocast.sqlite3" in cfg.db_path


def test_deployment_config_staging_isolation(monkeypatch, tmp_path):
    """Verifies staging environment isolates the database path to staging/."""
    monkeypatch.setenv("AEROCAST_ENV", "staging")
    monkeypatch.delenv("AEROCAST_DB_PATH", raising=False)
    monkeypatch.setenv("AEROCAST_DATA_DIR", str(tmp_path))

    cfg = DeploymentConfig.from_env()
    assert cfg.env == EnvironmentType.STAGING
    assert "staging" in cfg.db_path
    assert "aerocast_staging.sqlite3" in cfg.db_path


def test_deployment_config_testing_isolation(monkeypatch, tmp_path):
    """Verifies testing environment isolates the database path to testing/."""
    monkeypatch.setenv("AEROCAST_ENV", "testing")
    monkeypatch.delenv("AEROCAST_DB_PATH", raising=False)
    monkeypatch.setenv("AEROCAST_DATA_DIR", str(tmp_path))

    cfg = DeploymentConfig.from_env()
    assert cfg.env == EnvironmentType.TESTING
    assert "testing" in cfg.db_path
    assert "aerocast_testing.sqlite3" in cfg.db_path


def test_deployment_config_invalid_env(monkeypatch):
    """Verifies unparseable environment raises ConfigurationError."""
    monkeypatch.setenv("AEROCAST_ENV", "invalid_super_env")
    with pytest.raises(ConfigurationError) as exc:
        DeploymentConfig.from_env()
    assert "Invalid AEROCAST_ENV" in str(exc.value)


# -----------------------------------------------------------------------------
# 2. Fail-Fast Safety Invariants
# -----------------------------------------------------------------------------

def test_fail_fast_production_insecure_token(tmp_path):
    """Production must strictly reject default or weak admin tokens."""
    for token in INSECURE_TEST_TOKENS:
        cfg = DeploymentConfig(
            env=EnvironmentType.PRODUCTION,
            admin_token=token,
            secret_key="a" * 32,
            db_path=str(tmp_path / "aerocast.sqlite3"),
            data_mode="real",
            model_weights_path="dummy.keras"
        )
        with pytest.raises(ConfigurationError) as exc:
            cfg.validate()
        assert "FAIL FAST" in str(exc.value)


def test_fail_fast_production_short_credentials(tmp_path):
    """Production must reject admin token < 16 chars and secret key < 24 chars."""
    cfg_short_token = DeploymentConfig(
        env=EnvironmentType.PRODUCTION,
        admin_token="short_token",
        secret_key="a" * 32,
        db_path=str(tmp_path / "aerocast.sqlite3"),
        data_mode="real"
    )
    with pytest.raises(ConfigurationError):
        cfg_short_token.validate()

    cfg_short_secret = DeploymentConfig(
        env=EnvironmentType.PRODUCTION,
        admin_token="a" * 20,
        secret_key="short_secret",
        db_path=str(tmp_path / "aerocast.sqlite3"),
        data_mode="real"
    )
    with pytest.raises(ConfigurationError):
        cfg_short_secret.validate()


def test_fail_fast_production_dev_test_database(tmp_path):
    """Production must never allow pointing to dev/test databases."""
    for bad_db in ["dev.sqlite3", "test_db.sqlite3", "sample.sqlite3"]:
        cfg = DeploymentConfig(
            env=EnvironmentType.PRODUCTION,
            admin_token="secure_token_1234567890",
            secret_key="secure_secret_key_1234567890",
            db_path=str(tmp_path / bad_db),
            data_mode="real"
        )
        with pytest.raises(ConfigurationError) as exc:
            cfg.validate()
        assert "cannot use dev/test database" in str(exc.value)


def test_fail_fast_production_simulation_data_mode():
    """Production must reject simulation data mode."""
    prod_dir = Path("/tmp/aerocast_prod_sandbox")
    prod_dir.mkdir(parents=True, exist_ok=True)
    cfg = DeploymentConfig(
        env=EnvironmentType.PRODUCTION,
        admin_token="secure_token_1234567890",
        secret_key="secure_secret_key_1234567890",
        db_path=str(prod_dir / "aerocast.sqlite3"),
        data_mode="simulation"
    )
    with pytest.raises(ConfigurationError) as exc:
        cfg.validate()
    assert "cannot operate in 'simulation' DATA_MODE" in str(exc.value)


def test_fail_fast_cross_environment_staging_test():
    """Staging and testing must not point directly to production database."""
    prod_dir = Path("/tmp/aerocast_prod_sandbox")
    prod_dir.mkdir(parents=True, exist_ok=True)
    prod_db = str(prod_dir / "aerocast.sqlite3")
    
    cfg_staging = DeploymentConfig(
        env=EnvironmentType.STAGING,
        db_path=prod_db
    )
    with pytest.raises(ConfigurationError) as exc:
        cfg_staging.validate()
    assert "Staging environment cannot point directly to production" in str(exc.value)

    cfg_testing = DeploymentConfig(
        env=EnvironmentType.TESTING,
        db_path=prod_db
    )
    with pytest.raises(ConfigurationError) as exc:
        cfg_testing.validate()
    assert "Testing environment cannot point directly to production" in str(exc.value)


# -----------------------------------------------------------------------------
# 3. Database Migration Engine (Versioning, Backup Snapshots & Reversibility)
# -----------------------------------------------------------------------------

def test_migration_manager_lifecycle(tmp_path):
    """Tests the full migration lifecycle: status, migrate, backup, and rollback."""
    test_db = tmp_path / "test_migration.sqlite3"
    mgr = MigrationManager(str(test_db))

    # 1. Fresh status: all migrations should be unapplied
    status_init = mgr.status()
    assert len(status_init) == len(MIGRATIONS)
    assert all(not s["applied"] for s in status_init)

    # 2. Run migrate up to version 3
    applied_v3 = mgr.migrate(target_version=3)
    assert len(applied_v3) == 3
    assert [v for v, _ in applied_v3] == [1, 2, 3]

    # Verify tables created
    conn = sqlite3.connect(str(test_db))
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row[0] for row in cur.fetchall()}
    conn.close()

    assert "observations" in tables
    assert "predictions" in tables
    assert "raw_ingestion_log" in tables
    assert "model_artifacts" in tables
    assert "deployments" not in tables  # migration 5 not yet applied

    # 3. Re-run migration: idempotency check
    re_applied = mgr.migrate(target_version=3)
    assert len(re_applied) == 0

    # 4. Complete migration to latest version
    applied_remaining = mgr.migrate()
    assert len(applied_remaining) == len(MIGRATIONS) - 3
    assert mgr.get_applied_versions() == [1, 2, 3, 4, 5]

    # 5. Check deployments table exists
    conn = sqlite3.connect(str(test_db))
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='deployments';")
    assert cur.fetchone() is not None
    conn.close()

    # 6. Verify backup files were generated
    backup_files = list((tmp_path / "backups").glob("*.bak"))
    assert len(backup_files) >= 1

    # 7. Rollback down to version 4 (reverting migration 5)
    reverted = mgr.rollback(target_version=4)
    assert len(reverted) == 1
    assert reverted[0][0] == 5
    assert mgr.get_applied_versions() == [1, 2, 3, 4]

    # Verify additional backup was generated for rollback
    assert len(list((tmp_path / "backups").glob("*.bak"))) >= 2

    conn = sqlite3.connect(str(test_db))
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='deployments';")
    assert cur.fetchone() is None
    conn.close()


# -----------------------------------------------------------------------------
# 4. Containerization & Orchestration Manifest Sanity
# -----------------------------------------------------------------------------

def test_backend_dockerfile_sanity():
    """Verifies backend Dockerfile follows multi-stage non-root security principles."""
    root_dir = Path(__file__).parent.parent.resolve()
    df_path = root_dir / "backend" / "Dockerfile"
    assert df_path.exists(), "backend/Dockerfile must exist"

    content = df_path.read_text()
    assert "AS builder" in content, "Must use multi-stage build"
    assert "AS runtime" in content, "Must specify minimal runtime stage"
    assert "useradd" in content and "aerocast" in content, "Must create unprivileged user"
    assert "USER aerocast" in content, "Must execute as non-root user"
    assert "HEALTHCHECK" in content and "/ready" in content, "Must declare container readiness probe"
    assert "EXPOSE 8000" in content


def test_frontend_dockerfile_and_nginx_sanity():
    """Verifies frontend Dockerfile and Nginx reverse proxy configuration."""
    root_dir = Path(__file__).parent.parent.resolve()
    df_path = root_dir / "frontend" / "Dockerfile"
    assert df_path.exists(), "frontend/Dockerfile must exist"

    df_content = df_path.read_text()
    assert "FROM node:22-alpine AS builder" in content_or_str(df_content)
    assert "FROM nginxinc/nginx-unprivileged:alpine AS runtime" in df_content

    nginx_path = root_dir / "frontend" / "nginx.conf"
    assert nginx_path.exists(), "frontend/nginx.conf must exist"

    nginx_content = nginx_path.read_text()
    assert "proxy_pass http://backend:8000/api/;" in nginx_content
    assert "add_header X-Content-Type-Options \"nosniff\"" in nginx_content
    assert "gzip on;" in nginx_content
    assert "listen 8080" in nginx_content


def test_docker_compose_stacks_sanity():
    """Verifies all Docker Compose stacks are syntactically sound and isolated."""
    root_dir = Path(__file__).parent.parent.resolve()
    compose_files = [
        root_dir / "docker-compose.yml",
        root_dir / "docker-compose.staging.yml",
        root_dir / "docker-compose.prod.yml",
    ]

    for cf in compose_files:
        assert cf.exists(), f"{cf.name} must exist"
        text = cf.read_text()
        assert "services:" in text
        assert ("backend:" in text or "backend-staging:" in text)
        assert ("frontend:" in text or "frontend-staging:" in text)
        assert ("./data:/app/data" in text or "./data/staging:/app/data/staging" in text)

    # Production-specific assertions
    prod_text = (root_dir / "docker-compose.prod.yml").read_text()
    assert "internal: true" in prod_text, "Production backend must reside on internal network"
    assert "models:/app/models:ro" in prod_text, "Production model weights must be mounted read-only"


# -----------------------------------------------------------------------------
# 5. Release Manifest & Operational Tools Verification
# -----------------------------------------------------------------------------

def test_release_manifest_integrity():
    """Verifies release_manifest.json exists and conforms to provenance standards."""
    root_dir = Path(__file__).parent.parent.resolve()
    manifest_path = root_dir / "reports" / "release_manifest.json"
    assert manifest_path.exists(), "reports/release_manifest.json must exist"

    with open(manifest_path, "r") as f:
        data = json.load(f)

    assert "application" in data
    assert "release_version" in data
    assert "model_provenance" in data
    assert data["model_provenance"]["architecture"] == "ResAtt-ConvLSTM2D"
    assert data["model_provenance"]["parameter_count"] == 191524
    assert len(data["model_provenance"]["sha256_checksum"]) == 64
    assert data["database_provenance"]["current_schema_version"] == 5


def test_deploy_health_gate_script_sanity():
    """Verifies deploy_health_gate.sh exists and contains required probes."""
    root_dir = Path(__file__).parent.parent.resolve()
    script_path = root_dir / "scripts" / "deploy_health_gate.sh"
    assert script_path.exists()
    assert os.access(script_path, os.X_OK) or os.name != "posix"

    content = script_path.read_text()
    assert "/health" in content
    assert "/ready" in content
    assert "/api/system/health" in content
    assert "/api/radar-grid" in content


def test_rollback_model_script_sanity():
    """Verifies rollback_model.py exists and can execute 'list' command."""
    root_dir = Path(__file__).parent.parent.resolve()
    script_path = root_dir / "scripts" / "rollback_model.py"
    assert script_path.exists()

    result = subprocess.run(
        [sys_python(), str(script_path), "list"],
        capture_output=True,
        text=True,
        env=dict(os.environ, PYTHONPATH=str(root_dir / "backend"))
    )
    assert result.returncode == 0
    assert "Registered Models in Database" in result.stdout


# -----------------------------------------------------------------------------
# 6. Disaster Recovery & Scaling Reports Parity
# -----------------------------------------------------------------------------

def test_disaster_recovery_test_report_parity():
    """Verifies that automated DR drill reports are verified successful with RTO/RPO parity."""
    root_dir = Path(__file__).parent.parent.resolve()
    dr_report_path = root_dir / "reports" / "disaster_recovery_test.json"
    assert dr_report_path.exists(), "reports/disaster_recovery_test.json must exist"

    with open(dr_report_path, "r") as f:
        data = json.load(f)

    assert data.get("status") == "VERIFIED_SUCCESSFUL"
    assert data["integrity_check"] == "ok"
    assert data["recovery_objectives"]["measured_rto_seconds"] < 15.0
    for table_name, table_info in data["table_parity"].items():
        assert table_info["parity"] is True, f"Parity mismatch for table {table_name}"


def test_inference_benchmark_report_sanity():
    """Verifies that inference benchmark results exist with acceptable latency."""
    root_dir = Path(__file__).parent.parent.resolve()
    bench_path = root_dir / "reports" / "inference_benchmark.json"
    assert bench_path.exists(), "reports/inference_benchmark.json must exist"

    with open(bench_path, "r") as f:
        data = json.load(f)

    assert "timing_ms" in data
    assert data["timing_ms"]["inference_mean_ms"] < 500.0  # Safe threshold for CPU inference
    assert data["timing_ms"]["warmup_time_ms"] < 2000.0
    assert data["memory_mb"]["final_rss_mb"] > 0


# -----------------------------------------------------------------------------
# Helper Utilities
# -----------------------------------------------------------------------------

def content_or_str(s: str) -> str:
    return s

def sys_python() -> str:
    import sys
    return sys.executable

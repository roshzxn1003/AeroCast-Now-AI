# Runbook: AeroCast-Now AI Production Deployment & Release Management

**Component**: AeroCast-Now AI Deployment Engine  
**Severity Tier**: Operational / Critical  
**Target Environments**: Staging (`staging`), Production (`production`)  
**Target Hosts**: Containerized Docker Compose / Kubernetes  

---

## 1. Overview & Principles

This runbook guides operators through deploying, upgrading, and rolling back the **AeroCast-Now AI** platform.

### Core Deployment Invariants:
1. **Never commit secrets**: All credentials (`AEROCAST_ADMIN_TOKEN`, `AEROCAST_SECRET_KEY`, `IMD_API_KEY`) are injected at runtime via environment variables or secret vaults.
2. **Never connect production to dev/test databases**: The configuration engine enforces startup Fail-Fast termination if cross-environment paths are detected.
3. **Never deploy without migration backup**: SQLite migrations automatically create a timestamped WAL snapshot in `data/backups/` before applying any schema DDL.
4. **Never promote without passing Health Gates**: Production traffic is switched only after all 5 automated health gates pass.
5. **Non-root container execution**: Backend runs under UID `10001` (`aerocast`); Frontend runs under `nginxinc/nginx-unprivileged`.

---

## 2. Pre-Deployment Verification Checklist

Before triggering a production deployment, ensure the following prerequisites are met:

- [ ] **Release Tag & Commit**: Verify commit SHA has passed CI (`.github/workflows/ci.yml`).
- [ ] **Release Manifest**: Generate and inspect `reports/release_manifest.json`:
  ```bash
  python scripts/generate_release_manifest.py --tag v2.1.0
  ```
- [ ] **Model Weight Integrity**: Verify production model weights checksum:
  ```bash
  sha256sum backend/models/convlstm_real_best.keras
  # Match with release manifest: 6194f04a8ae4756dca8bf11d4627c350873bec25c8ad20e0b0ca9137fc603e87
  ```
- [ ] **Environment Configuration**: Validate `.env.production` contains secure tokens:
  - `AEROCAST_ENV=production`
  - `DATA_MODE=real` (or `hybrid`)
  - `AEROCAST_ADMIN_TOKEN` $\ge 16$ characters, random alphanumeric.
  - `AEROCAST_SECRET_KEY` $\ge 24$ characters, random alphanumeric.
  - No references to `dev`, `test`, or `sample` in `AEROCAST_DB_PATH`.

---

## 3. Step-by-Step Deployment Procedure

### Step 3.1: Database Pre-Migration & Backup
Always execute schema migrations before bringing up new application containers:
```bash
# Verify current migration status
cd backend
PYTHONPATH=. python -m db.migrations status

# Apply pending migrations (automatically creates pre-migration backup)
PYTHONPATH=. python -m db.migrations migrate

# Verify all migrations show APPLIED
PYTHONPATH=. python -m db.migrations status
```

### Step 3.2: Container Image Build & Staging Validation
```bash
# 1. Build and launch staging environment
docker compose -f docker-compose.staging.yml build --no-cache
docker compose -f docker-compose.staging.yml up -d

# 2. Run Health Gate against Staging
./scripts/deploy_health_gate.sh http://localhost:8080

# 3. If staging gates succeed, tear down or keep for soak testing:
docker compose -f docker-compose.staging.yml down
```

### Step 3.3: Production Release Execution
```bash
# 1. Build production containers
docker compose -f docker-compose.prod.yml build

# 2. Launch production stack in background
docker compose -f docker-compose.prod.yml up -d

# 3. Wait for startup period (45s) and evaluate Health Gate
./scripts/deploy_health_gate.sh http://localhost:80
```

### Step 3.4: Post-Deployment Smoke Verification
Run an end-to-end inference benchmark to verify CPU/GPU performance matches acceptable envelope:
```bash
python scripts/benchmark_inference.py 10
# Verify: Mean latency < 200 ms on CPU; P99 < 300 ms.
```

---

## 4. Emergency Rollback Procedures

If any post-deployment anomalies arise (high error rate, latency spike, model hallucination):

### Procedure 4.1: Fast Application Container Rollback
To immediately revert to the previous container image version:
```bash
# Revert to previous git release tag
git checkout <PREVIOUS_RELEASE_TAG>

# Rebuild and restart production stack
docker compose -f docker-compose.prod.yml up -d --build
./scripts/deploy_health_gate.sh http://localhost:80
```

### Procedure 4.2: Hot Model Rollback (Zero-Downtime)
If the application is healthy but the newly promoted model exhibits meteorological drift:
```bash
# 1. List registered models
python scripts/rollback_model.py list

# 2. Execute zero-downtime hot rollback
python scripts/rollback_model.py rollback "ops_lead" "Severe precipitation bias detected in +60m forecast" "1.0.0"

# 3. Verify hot-reloaded model in health probe
curl -s http://localhost:80/api/health | jq .model_version
```

### Procedure 4.3: Database Schema Rollback
If a newly applied database migration caused functional regression:
```bash
cd backend
# Rollback down to previous target version (e.g., version 4)
PYTHONPATH=. python -m db.migrations rollback 4
```

### Procedure 4.4: Disaster Recovery Full Restore
In case of catastrophic database corruption:
```bash
python scripts/backup_restore_test.py
# Or manual restore from latest hourly snapshot:
sqlite3 data/aerocast.sqlite3 ".restore data/backups/aerocast_latest.sqlite3.bak"
```

---

## 5. Post-Deployment Observability Checklist

After deployment succeeds, monitor the following metrics for at least 30 minutes:

| Probe / Metric | Target Value | Verification Command |
| :--- | :--- | :--- |
| **Liveness** | HTTP 200 `HEALTHY` | `curl -s http://localhost:80/health` |
| **Readiness** | HTTP 200 `HEALTHY` | `curl -s http://localhost:80/ready` |
| **Active Connections** | Stable, no leak | `curl -s http://localhost:80/api/system/concurrency` |
| **Process RSS Memory** | $< 1.5\text{ GB}$ | `curl -s http://localhost:80/api/system/resources` |
| **Inference Mean Latency** | $< 180\text{ ms}$ | `curl -s http://localhost:80/api/radar-grid?channel=dbz` |
| **Nginx Access Log** | HTTP 200 / 304 | `docker logs aerocast-frontend-prod | tail -n 50` |
| **Backend Structured Log** | No unhandled `ERROR` | `docker logs aerocast-backend-prod | tail -n 50` |

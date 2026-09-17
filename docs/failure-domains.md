# System Failure Domain Model — AeroCast-Now AI

## 1. Architectural Failure Domains
AeroCast-Now AI decomposes operational responsibilities into discrete, decoupled failure domains to prevent cascading systemic failure:

```
                            ┌──────────────────────────────────────┐
                            │           AEROCAST PLATFORM          │
                            └──────────────────┬───────────────────┘
                                               │
           ┌───────────────────────────────────┼───────────────────────────────────┐
           ▼                                   ▼                                   ▼
┌─────────────────────┐             ┌─────────────────────┐             ┌─────────────────────┐
│  DOMAIN A: DATA     │             │  DOMAIN B: COMPUTE  │             │  DOMAIN C: STATE    │
│  External Ingestion │             │  API & Inference    │             │  Database & Storage │
└──────────┬──────────┘             └──────────┬──────────┘             └──────────┬──────────┘
           │                                   │                                   │
     ┌─────┴─────┐                       ┌─────┴─────┐                       ┌─────┴─────┐
     ▼           ▼                       ▼           ▼                       ▼           ▼
Upstream     Raw Disk                API Host    ML Engine               SQLite      File Archive
Providers    Buffer                  (FastAPI)   (ResAtt-ConvLSTM)       WAL         Artifacts
                                               │
                                               ▼
                                    ┌─────────────────────┐
                                    │  DOMAIN D: CLIENT   │
                                    │  React / WebGL UI   │
                                    └─────────────────────┘
```

---

## 2. Domain Isolation Boundaries & Degradation Rules

### Domain A: Atmospheric Data Ingestion
* **External Dependencies**: IMD Doppler Radars, Blitzortung Lightning Network, INSAT-3D/3DR Satellite, Open-Meteo NWP.
* **Failure Modes**: Upstream network outage, HTTP 504/timeout, corrupted radar raster, rate-limiting from public gateways.
* **Isolation Guarantee**:
  * Outages are contained within Domain A using per-provider **Circuit Breakers**.
  * When a primary provider fails, the system automatically falls back to secondary providers (e.g. RainViewer for radar, ECMWF/GFS for NWP).
  * If lightning data is temporarily unavailable, the model gracefully degrades to radar-only mode with appropriate operational flags (`lightning_missing = True`).
  * Ingestion failures **never** crash the API server or prevent historical forecast verification.

### Domain B: API Gateway & ML Inference
* **Internal Subsystems**: FastAPI router, Pydantic validation, inference concurrency semaphore, ResAtt-ConvLSTM2D execution.
* **Failure Modes**: High request concurrency, GPU/CPU RAM saturation, numerical divergence (NaN output), worker process termination.
* **Isolation Guarantee**:
  * An **Inference Concurrency Semaphore** bounds concurrent model evaluations (max 2 concurrent CPU/GPU jobs), shedding excess load with HTTP 503 instead of crashing the process.
  * Numerical safety sanitizers intercept and reject NaN/Inf predictions before persistence.
  * Heavy inference calls do not block fast read probes (`/health`, `/live`, `/metrics`).

### Domain C: Persistent State & Storage
* **Internal Subsystems**: SQLite database (`aerocast.sqlite3`), WAL journal, raw raster buffer (`data/raw/`), model weight directory (`models/`).
* **Failure Modes**: Database lock contention, disk space exhaustion, permission errors, artifact corruption.
* **Isolation Guarantee**:
  * SQLite operates in **Write-Ahead Logging (WAL)** mode with connection timeouts and jittered retries on `OperationalError: database is locked`.
  * Atomic multi-table writes occur within explicit transactions; rollbacks preserve state consistency.
  * Model artifacts are verified via SHA-256 prior to loading. If an artifact is corrupt, the system falls back to archived previous production weights.

### Domain D: Client Presentation (Frontend)
* **Subsystems**: React SPA, Three.js WebGL globe, district threat bulletin cards.
* **Failure Modes**: Backend unreachable, WebSocket disconnection, WebGL context loss.
* **Isolation Guarantee**:
  * Client implements exponential backoff reconnection with jitter.
  * Stale data is explicitly highlighted with relative timestamps ("Updated 5m ago - STALE").
  * Local browser caching allows viewing previously rendered district advisories even during complete network disconnection.

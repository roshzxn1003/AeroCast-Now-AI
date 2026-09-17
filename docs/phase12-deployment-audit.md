# Phase 12 Deployment Audit: AeroCast-Now AI

**Generated**: 2026-09-17  
**Status**: Completed  
**Repository**: `https://github.com/roshzxn1003/AeroCast-Now-AI`  
**Target Systems**: FastAPI Backend (8000), React/Vite Frontend (5173/80), Streamlit Meteorological Dashboard (8501)

---

## 1. Executive Summary

This audit assesses the deployment, infrastructure, scaling, and operational reliability characteristics of **AeroCast-Now AI** following the completion of Phases 8 through 11. The application currently operates as an asynchronous, multi-modal atmospheric nowcasting platform combining deep learning (ResAtt-ConvLSTM2D), real-time observational ingestion (Radar, Satellite, Lightning, NWP), and interactive geospatial frontends.

Prior to Phase 12:
- Services were managed via local shell scripts (`start_all.sh`, `stop_all.sh`) or direct developer terminal processes.
- An outdated single-stage `backend/Dockerfile` targeted Streamlit alone on port 8501, neglecting the primary FastAPI REST engine and Vite frontend.
- No unified `docker-compose.yml` or container orchestration manifests existed.
- No continuous integration (CI) workflows existed in `.github/workflows/`.
- Environment configurations lacked formal environment separation (`development`, `testing`, `staging`, `production`) and startup fail-fast validation.

Phase 12 builds a robust, reproducible, and secure deployment architecture while honoring the fundamental engineering truth: **deployment and containerization do not constitute meteorological certification**.

---

## 2. Component Inventory & Runtime Audit

### 2.1 Backend Services
| Property | Specification |
| :--- | :--- |
| **Framework** | FastAPI 0.115+ on Uvicorn (ASGI) |
| **Python Version** | 3.12.13 (Virtualenv at `venv/`) |
| **Primary Entrypoint** | `backend/api_server.py:app` |
| **Secondary Entrypoint** | `backend/app.py` (Streamlit Scientific Dashboard) |
| **Listening Ports** | `8000` (FastAPI REST & Websockets), `8501` (Streamlit) |
| **Core Responsibilities** | 4-channel spatio-temporal tensor fusion, ConvLSTM2D inference, SCIT kinematic storm cell tracking, 2σ lightning jump precursor detection, Common Alerting Protocol (CAP v1.2) generation, multi-cadence observation ingestion. |
| **Failure Domains** | Ingestion feeds (IMD, Blitzortung, INSAT, Open-Meteo), SQLite DB locking, model weight corruption, CPU/Memory resource exhaustion. |

### 2.2 Frontend Application
| Property | Specification |
| :--- | :--- |
| **Framework** | React 19, TypeScript 5.x, Vite 6.x |
| **Styling & Rendering** | TailwindCSS 4, Three.js, Globe.gl (WebGL), Recharts, Lucide Icons |
| **Build Tooling** | `tsc -b && vite build` (Output: `frontend/dist/`) |
| **Dev Port** | `5173` (Vite dev server with `/api` reverse proxy to `http://localhost:8000`) |
| **Prod Port** | `80` / `443` (Nginx static reverse proxy) |
| **Bundle Characteristics** | Chunk splitting implemented: `globe` (Three.js/Globe.gl: ~1.98 MB uncompressed / 559 kB gzip), `charts` (Recharts: ~359 kB / 94 kB gzip), `index` (~482 kB / 136 kB gzip). Total static bundle: ~2.9 MB uncompressed. |

### 2.3 Machine Learning & Model Artifacts
| Property | Specification |
| :--- | :--- |
| **Model Family** | Spatio-Temporal Residual-Attention ConvLSTM2D (`ResAtt-ConvLSTM2D`) |
| **Parameter Count** | 191,524 parameters |
| **Framework** | TensorFlow 2.15+ / Keras 3.x |
| **Input Shape** | `(Batch, T_in=4, Height=32, Width=32, Channels=4)` |
| **Output Shape** | `(Batch, T_out=4, Height=32, Width=32, Channels=4)` for +15m, +30m, +45m, +60m horizons |
| **Production Artifact** | `backend/models/convlstm_real_best.keras` (2,356,306 bytes, SHA-256 registered) |
| **Auxiliary Artifacts** | `scaler.pkl` (879 bytes), `scaler_params.json` (742 bytes), `model_metadata_real.json` (4,430 bytes) |
| **Inference Compute** | Dual-mode: Native CPU (AVX2/FMA vector acceleration) or NVIDIA GPU (CUDA 12+). Tested latency: ~28–45 ms on modern x86_64 CPU; ~10–15 ms on CUDA GPU. |

---

## 3. Storage & Persistence Architecture

The following directories and files constitute persistent state that **must never reside on ephemeral container writable layers**:

1. **Relational Database (`data/aerocast.sqlite3`)**:
   - Size: ~1.15 MB baseline, grows with operational nowcasts, verification records, audit logs, and idempotency keys.
   - Operating Mode: SQLite with Write-Ahead Logging (`WAL`), `PRAGMA synchronous = NORMAL`.
   - Symlink note: `backend/data` is currently a symlink to `../data`. In containerized environments, the volume must be mounted explicitly at `/app/data`.
2. **Raw Atmospheric Ingestion Storage (`data/raw/`)**:
   - Subdirectories: `data/raw/radar/`, `data/raw/satellite/`, `data/raw/lightning/`, `data/raw/weather/`.
   - Deduplicated by SHA-256 payload hash in `raw_ingestion_log`.
3. **Processed Datasets & Historical Sequences (`data/datasets/`, `data/sequences/`, `data/processed/`)**:
   - Normalized multi-modal tensors used for offline evaluation and candidate retraining.
4. **Model Artifacts & Registry (`backend/models/`)**:
   - Checked-in baseline weights and runtime metadata. Retrained models transition from `staging/` to `production/` only upon explicit operator approval.
5. **Operational Logs (`logs/` / `*.log`)**:
   - Structured JSON logs formatted by `StructuredJSONFormatter` with secret masking.

---

## 4. Environment Configuration & Variables

Currently, configuration is partially loaded from `.env` and defaults in `data_config.py`. The audit identified the following variables:

| Variable | Current Default | Security Risk / Operational Role |
| :--- | :--- | :--- |
| `AEROCAST_ENV` | *(Implicit / undefined)* | **Critical**: Must distinguish `development`, `testing`, `staging`, `production`. |
| `DATA_MODE` | `hybrid` | Controls data source fallback (`hybrid`, `real`, `simulation`). |
| `AEROCAST_DB_PATH` | `../data/aerocast.sqlite3` | Path to persistent SQLite database file. |
| `IMD_API_KEY` | *(Empty string)* | External API credential (must never be committed). |
| `IMD_API_URL` | `https://api.imd.gov.in/public/index.php` | Radar API upstream. |
| `OPEN_METEO_URL` | `https://api.open-meteo.com/v1/forecast` | Keyless NWP sounding provider. |
| `BLITZORTUNG_ENABLED` | `true` | Real-time lightning strike WebSocket/TCP feed. |
| `HOST` / `PORT` | `0.0.0.0` / `8000` | Binding configuration. |
| `VITE_API_URL` | `http://localhost:8000` | Frontend backend target (must support container networking). |
| `AEROCAST_ADMIN_TOKEN` | *(Hardcoded test fallback)* | Must be required and securely generated in `production`. |

---

## 5. Security & Isolation Deficiencies Identified

1. **Missing Formal Environment Boundaries**: No automated checks prevent a production instance from running against a development or testing database.
2. **Outdated Dockerfile**: Existing `backend/Dockerfile` only starts Streamlit as `root` user, lacks non-root isolation, lacks FastAPI backend entrypoint, and has no multi-stage caching.
3. **Missing Frontend Containerization**: No production Nginx container for the React SPA.
4. **No Container Compose Orchestration**: Developers must run disparate processes manually.
5. **No Automated CI Pipeline**: No `.github/workflows/` automated linting, test execution, or build verification.
6. **Hardcoded API Fallbacks in Frontend**: Frontend `api.ts` defaulted strictly to `/api`, which works under Vite dev proxy but requires formal Nginx reverse-proxy rules in production.

---

## 6. Scaling Bottlenecks & Resource Characteristics

1. **SQLite Concurrent Writes**: SQLite WAL allows concurrent readers but single-writer serialization. Saturated write bursts must be guarded via exponential jitter retries (established in Phase 11) or queued.
2. **Inference Concurrency**: TensorFlow/Keras forward pass allocates memory dynamically. Phase 11 implemented an asynchronous semaphore (`MAX_CONCURRENT_INFERENCES = 2`) which successfully prevents OOM panics.
3. **Provider Rate Limiting**: Upstream Open-Meteo and IMD endpoints have rate limits; local cache TTLs (300s to 900s) are essential to prevent upstream 429 throttling.
4. **Frontend Asset Weight**: The 3D WebGL Globe component (~1.98 MB) should be served with gzip/brotli compression and long-term HTTP caching headers in production.

---

## 7. Audit Conclusion & Phase 12 Action Plan

To transition AeroCast-Now AI into a fully deployable, scalable, and resilient system without sacrificing simplicity, Phase 12 will deliver:
1. Formal environment definitions (`development`, `testing`, `staging`, `production`) with fail-fast validation.
2. Production-hardened multi-stage Dockerfiles for backend and frontend with non-root security.
3. Multi-environment Docker Compose stacks (`docker-compose.yml`, `docker-compose.staging.yml`, `docker-compose.prod.yml`).
4. Automated SQLite database migration engine with version tracking.
5. GitHub Actions CI/CD workflows covering backend tests, frontend builds, and security audits.
6. Benchmarked CPU/GPU performance measurements and realistic scaling analyses.
7. Automated backup, restore, and disaster recovery validation test suites.
8. Comprehensive deployment runbooks and operational checklists.

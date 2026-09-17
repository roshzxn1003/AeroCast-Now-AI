# Phase 9: Operational Data Infrastructure, Multi-Source Ingestion & Redundancy Audit

**Date:** 2026-09-16  
**System:** AeroCast-Now AI Pro  
**Scope:** Complete audit of data ingestion, normalization, providers, redundancy, storage, and inference handoff.

---

## 1. Executive Summary

This document establishes the baseline architecture for **Phase 9: Operational Data Infrastructure, Multi-Source Ingestion & Redundancy**.

During Phase 8, the project established:
- An operational SQLite Write-Ahead Logging (`WAL`) persistence store (`observations`, `predictions`, `verifications`, `alerts`, `model_registry`, `audit_log`).
- An atmospheric quality control engine (`AtmosphericQualityControl`) with physical boundaries and quality flags (`VALID`, `SUSPECT`, `MISSING`, `STALE`, `INVALID`).
- A singleton, non-blocking asynchronous `ModelManager` with automated startup warmup and AVX2/FMA vector hardware detection.
- A model registry with staged promotion gates (`TRAINING` → `VALIDATION` → `STAGING` → `PRODUCTION` → `RETIRED`) and instant rollback.
- Removal of critical data fabrication (unconditional `has_jump=True` replaced with honest empirical checks, Chennai DWR station code mapped to authentic `chn`/`sri`, TLS/SSL enabled by default).

However, the **data ingestion and synchronization tier** currently exhibits several architectural shortcomings that must be systematically engineered in Phase 9 to meet operational meteorological standards:
1. Provider coupling: Ingestion is fragmented between legacy scraping functions in `real_data_service.py`, `live_data_service.py`, and newer provider wrappers in `backend/providers/` and `backend/data_ingestion/`.
2. Silent provider fallback: Fallbacks between IMD and RainViewer or synthetic data occur without recording structured fallback events or degradation reasons.
3. No canonical observation schema: Observations are passed as ad-hoc dictionaries or numpy arrays rather than a strongly typed, checksummed canonical schema.
4. Lacking circuit breaker & backoff: Failed network requests retry naively or timeout during client HTTP requests.
5. Incomplete raw data preservation: Raw HTTP responses, GIFs, and JSON payloads are partially cached on disk without an organized raw observation lake retaining provenance and SHA-256 hashes.
6. Temporal synchronization & missingness: Incomplete observations (e.g., radar down but satellite up) are either synthesized or cause partial failures rather than explicitly flagging missingness and calculating domain coverage.
7. Lack of replay mechanism: No unified historical replay engine exists to stream historical events through the exact same pipeline at selectable playback speeds (1x, 10x, 100x).

---

## 2. Current Ingestion Flow & Data Sources

| Sensor / Domain | Primary Upstream | Fallback Upstream | Ingestion Method | Cadence | Spatial Extent |
|:---|:---|:---|:---|:---|:---|
| **Doppler Radar (dBZ, VIL)** | IMD Mausam DWR Portal (`mausam.imd.gov.in`) | RainViewer Global API (`api.rainviewer.com`) | HTTP GIF scrape / REST PNG tile decode | 10–15 min | 11 IMD stations, 250 km radius |
| **Geostationary Satellite (TIR 10.8µm)** | IMD / MOSDAC INSAT-3D/3DR | Open-Meteo Cloud Cover / ERA5 | HTTP JPEG scrape (`3Dasiasec_ir1.jpg`) | 15–30 min | Indian Subcontinent & oceanic basin |
| **Lightning Strikes (IC/CG)** | Blitzortung Community LDN | Synthetic Poisson Generator | WebSocket (`wss://*.blitzortung.org`) | Real-time stream (10–60s buffer) | Pan-India bounding box (`6–38°N, 68–98°E`) |
| **NWP & Atmospheric Sounding** | Open-Meteo GFS/ECMWF Analysis | Static Station Climatology Table | REST API JSON | 1–3 hours | Point coordinates per station / district |
| **Surface Weather AWS** | Open-Meteo Surface APIs | None (fails to None) | REST API JSON | 15–60 min | Station gazetteer |

---

## 3. Current Synthetic Data Usage & Leakage Analysis

| Component | Current Implementation | Phase 9 Requirement | Action Required |
|:---|:---|:---|:---|
| `observation_service.py` | `data_mode="auto"` silently synthesizes storm fields when real radar < 18 dBZ and blends 50% with satellite | Strict mode separation: `REAL`, `SIMULATION`, `REPLAY`, `TEST`. In `REAL` mode, never synthesize storms. | Refactor `observation_service.py` to enforce explicit data modes. |
| `district_nowcast_service.py` | Synthesizes sounding indices using base cape formula if real sounding fails | In `REAL` mode, preserve `None` or use real NWP analysis. Flag imputation explicitly. | Replace heuristic sounding synthesis with real Open-Meteo sounding and explicit imputation metadata. |
| `nowcasting_engine.py` | `identify_and_track_storm_cells` had randomized speed (`42 ± 5 km/h`) | Centroid tracking across consecutive frames or report `motion_source: UNAVAILABLE` | Implemented real frame-to-frame displacement. |

---

## 4. Current Storage & Schema

### Current Database
SQLite database at `data/aerocast.sqlite3` operating under Write-Ahead Logging (`WAL`) mode with tables:
1. `observations`: Basic observation storage with `quality_status` and `processing_version`.
2. `predictions`: Immutable forecast ledger with `prediction_id`, model metadata, and valid time.
3. `verifications`: WMO contingency scores (CSI, POD, FAR, HSS) and location error.
4. `alerts`: CAP v1.2 alert store with lifecycle states.
5. `model_registry`: Model promotion and rollback tracking.
6. `audit_log`: Operational actions audit log.

### Storage Gaps
- Raw payloads are stored as JSON text inside the database rather than preserving raw binary files (GIF, JPG, GeoJSON, raw JSON) in a structured raw data lake (`data/raw/<domain>/<YYYY>/<MM>/<DD>/`).
- Observations table lacks structured support for raster grids, tile references, and checksumming.

---

## 5. Current Model Input Interface

- **Input Tensor Shape:** `(1, 4, 32, 32, 4)` representing:
  - Timesteps: 4 temporal steps ($T_{-45}, T_{-30}, T_{-15}, T_0$) spaced at 15-minute intervals.
  - Height × Width: $32 \times 32$ pixels covering a $128 \times 128\text{ km}$ spatial domain ($4\text{ km}$ spatial resolution).
  - Channels:
    - Channel 0: Radar Reflectivity $\text{dBZ} \in [0.0, 75.0]$ normalized by $75.0$.
    - Channel 1: Vertically Integrated Liquid $\text{VIL} \in [0.0, 65.0]\text{ kg/m}^2$ normalized by $65.0$.
    - Channel 2: INSAT-3D Thermal IR Brightness Temperature $\text{TIR} \in [-85.0, +35.0]^\circ\text{C}$ normalized via $(35.0 - \text{TIR}) / 120.0$.
    - Channel 3: Lightning Flash Density $\in [0.0, 25.0]\text{ flashes/km}^2$ normalized by $25.0$.
- **Model Output Shape:** `(1, 4, 32, 32, 4)` for $+15, +30, +45, +60\text{ min}$, with autoregressive rollout to $+90, +120\text{ min}$.
- **Resolution Constraint:** The ML model architecture expects $(32, 32, 4)$. All geospatial regridding must produce this canonical grid for model consumption without altering model weights.

---

## 6. Components to Reuse vs. Components to Refactor

### Reusable Components (Keep & Enhance)
- `backend/db/database.py`: High-performance SQLite WAL connection manager.
- `backend/core/quality_control.py`: Physical boundary definitions and quality checks.
- `backend/ml/model_manager.py`: Singleton async model loader and warmup.
- `backend/ml/model_registry.py`: Staging, promotion, rollback logic.
- `backend/verification/verification_engine.py`: WMO contingency scoring and location error tracking.
- `backend/providers/base_provider.py`: Base provider interface and `ProviderResult`.
- `backend/dataset_pipeline/spatial_grid.py`: Coordinate projection and regridding routines.
- `backend/dataset_pipeline/scaler.py`: `ChannelScaler` normalization formulas.

### Components Requiring Refactoring / New Implementations
1. **Canonical Observation Schema (`backend/core/canonical_observation.py`):**
   - Create a typed, universal observation schema supporting scalar, gridded raster, time-series, and cell geometries.
2. **Provider Manager & Redundancy Engine (`backend/ingestion/provider_manager.py`):**
   - Implement Primary / Secondary adapter routing with bounded retry, exponential backoff, circuit breaking, and transparent fallback recording.
3. **Multi-Cadence Ingestion Scheduler (`backend/ingestion/scheduler.py`):**
   - Separate ingestion cadences for radar (10m), satellite (15m), lightning (1m/streaming), and NWP (1h).
4. **Idempotent Ingestion & Raw Lake (`backend/ingestion/raw_storage.py`):**
   - Deterministic SHA-256 deduplication and raw file archival (`data/raw/...`).
5. **Temporal Synchronizer & Missingness Engine (`backend/ingestion/temporal_sync.py`):**
   - Synchronize observations into $T_{-45}, T_{-30}, T_{-15}, T_0$ slots; explicitly mark missingness and calculate coverage percentage.
6. **Inference Readiness Gate (`backend/ingestion/inference_gate.py`):**
   - Evaluate data quality, freshness, and domain coverage before handoff to `ModelManager`. Return `READY`, `DEGRADED`, or `BLOCKED`.
7. **Historical Replay Engine (`backend/ingestion/replay_engine.py`):**
   - Deterministically replay historical raw datasets at variable speeds ($1\times, 10\times, 100\times$) for scientific verification.
8. **Operational Data Dashboard APIs:**
   - Expose `/data/sources`, `/data/health`, `/data/freshness`, `/data/coverage`, `/data/quality`, `/data/replay`.

---
*Audit completed and documented.*

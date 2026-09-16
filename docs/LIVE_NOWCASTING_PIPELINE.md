# AeroCast-Now AI — Phase 5: Live Real-Data Pipeline & Inference Architecture

## Executive Overview

Phase 5 completes the end-to-end integration of the AeroCast-Now AI system:
```text
┌────────────────────────┐     ┌────────────────────────┐     ┌────────────────────────┐
│  LIVE ATMOSPHERIC FEEDS│ ──> │   ROLLING 15-MIN BUFFER│ ──> │  CONVLSTM REAL MODEL   │
│  Radar, INSAT-3D, LDN  │     │   T-45, T-30, T-15, T0 │     │   (191,524 parameters) │
└────────────────────────┘     └────────────────────────┘     └────────────────────────┘
                                                                           │
                                                                           ▼
┌────────────────────────┐     ┌────────────────────────┐     ┌────────────────────────┐
│ 3D GLOBE VISUALIZATION │ <── │  FASTAPI REST SERVICE  │ <── │ METEOROLOGICAL PRODUCTS│
│ Mode Badge, Freshness  │     │  /api/live/nowcast     │     │ SCIT, Jump, CAP v1.2   │
└────────────────────────┘     └────────────────────────┘     └────────────────────────┘
```

---

## 1. Provider Architecture (`backend/providers/`)

Every atmospheric data source implements [`BaseObservationProvider`](file:///home/arun-roshan-gj/SIH/backend/providers/base_provider.py), enforcing physical sanity bounds, latency measurement, and freshness categorization:

| Provider | File | Primary Feed | Fallback Feed | Output Tensor / Physical Bounds |
|---|---|---|---|---|
| **Radar** | [`radar_provider.py`](file:///home/arun-roshan-gj/SIH/backend/providers/radar_provider.py) | IMD Doppler Weather Radar GIF products | RainViewer Pan-India Radar Tile Mosaic | Channel 0: dBZ $[0, 75]$<br>Channel 1: VIL $[0, 65]\text{ kg/m}^2$ |
| **Satellite** | [`satellite_provider.py`](file:///home/arun-roshan-gj/SIH/backend/providers/satellite_provider.py) | ISRO/IMD INSAT-3D/3DR TIR1 ($10.8\,\mu\text{m}$) | Cached Geostationary Frame | Channel 2: TIR Brightness Temp $[-85, +35]^\circ\text{C}$ |
| **Lightning** | [`lightning_provider.py`](file:///home/arun-roshan-gj/SIH/backend/providers/lightning_provider.py) | Blitzortung.org Live CG/IC Network | Cached LDN Strikes Buffer | Channel 3: Flash Density $[0, 25]\text{ flashes/km}^2$<br>Flash Rate (fpm) |
| **Weather** | [`weather_provider.py`](file:///home/arun-roshan-gj/SIH/backend/providers/weather_provider.py) | IMD AWS Network | Open-Meteo High-Resolution Convective Analysis | Convective Sounding (CAPE, CIN, LI, Shear, PWAT) |

### Meteorological Freshness Criteria
- **FRESH**: $\text{Age} \le 20\text{ minutes}$ (standard radar volume & satellite scan latency)
- **DELAYED**: $20 < \text{Age} \le 60\text{ minutes}$
- **STALE**: $\text{Age} > 60\text{ minutes}$
- **MISSING**: Stream offline or null response
- **INVALID**: Out of physical bounds / corrupt tensor dimensions

---

## 2. Rolling Buffer & Synchronization (`backend/live/`)

- [`ObservationManager`](file:///home/arun-roshan-gj/SIH/backend/live/observation_manager.py) manages a FIFO buffer of 4 frames at 15-minute intervals: $T-45, T-30, T-15, T_0$.
- **Strict Scientific Honesty**:
  - In `DATA_MODE=real`: If fewer than 4 live frames are buffered, returns `sequence_ready: false` with explanation `"Awaiting frame accumulation"`. **Never invents observations or predictions.**
  - In `DATA_MODE=hybrid`: Uses latest live data; missing historical slots are warmed up from the latest live frame with physical advection/attenuation, marked with `provenance: "HYBRID"`.
  - In `DATA_MODE=simulation`: Generates procedural synthetic convective fields for demonstration, marked with `provenance: "SIMULATION"`.

---

## 3. ML Inference Service (`backend/ml/`)

- [`ModelLoader`](file:///home/arun-roshan-gj/SIH/backend/ml/model_loader.py): Singleton loader caching `backend/models/convlstm_real_best.keras` (191,524 parameters) and fitted `ChannelScaler` (`data/processed/scaler.pkl`).
- [`LiveInferenceService`](file:///home/arun-roshan-gj/SIH/backend/ml/inference_service.py):
  1. Input: $(4, 32, 32, 4)$ physical sequence.
  2. Normalization: Scaled to $[0.0, 1.0]$ via fitted `ChannelScaler`.
  3. ConvLSTM Forward Pass: Generates $+15, +30, +45, +60$ minute lead time grids.
  4. Postprocessing via [`PredictionPostprocessor`](file:///home/arun-roshan-gj/SIH/backend/ml/prediction_postprocessor.py):
     - Inverse transform back to physical units (dBZ, VIL, TIR, Flash).
     - SCIT / TITAN storm cell identification and centroid tracking.
     - 2-sigma lightning jump detection ($2\sigma$ rapid electrification threshold).
     - Common Alerting Protocol (CAP v1.2) XML/JSON structured alert bulletin.
     - Sparse downsampled heatmap coordinates for bandwidth-efficient 3D globe rendering.

---

## 4. FastAPI Endpoints (`backend/api_server.py`)

### `GET /api/live/nowcast`
**Parameters**:
- `station` (default: `"Chennai DWR (Sriharikota/Port)"`)
- `storm_mode` (default: `"Severe Squall Line"`)
- `forecast_steps` (default: `4`, range: 1..6)
- `data_mode` (`"hybrid"`, `"real"`, `"simulation"`)

**Response Example (Hybrid Mode)**:
```json
{
  "mode": "hybrid",
  "provenance": "LIVE_REAL_DATA",
  "data_note": "HYBRID DATA — Real-world radar/satellite observations aligned with active convective background.",
  "sequence_ready": true,
  "station": "Chennai DWR (Sriharikota/Port)",
  "location": { "lat": 13.0827, "lon": 80.2707 },
  "state": "Tamil Nadu",
  "observation_timestamp": "2026-09-15T15:55:46Z",
  "prediction_timestamp": "2026-09-15T15:55:47Z",
  "inference_time_ms": 383.8,
  "freshness": {
    "overall_status": "fresh",
    "streams": {
      "radar": { "status": "fresh", "age_minutes": 8.5, "source": "LIVE-RAINVIEWER" },
      "satellite": { "status": "fresh", "age_minutes": 14.0, "source": "LIVE-INSAT-3D" },
      "lightning": { "status": "fresh", "age_minutes": 1.5, "source": "LIVE-BLITZORTUNG-LDN" },
      "weather": { "status": "fresh", "age_minutes": 10.2, "source": "OPEN-METEO" }
    }
  },
  "observation": {
    "max_dbz": 48.5,
    "max_vil": 26.2,
    "min_tir_c": -52.4,
    "flash_rate_fpm": 18.0,
    "storm_cells": [ ... ],
    "dbz_grid": [ ... ]
  },
  "forecast": [
    { "lead_time_min": 15, "max_dbz": 51.2, "max_vil": 30.1, "cells": [ ... ] },
    { "lead_time_min": 30, "max_dbz": 53.0, "max_vil": 33.4, "cells": [ ... ] },
    { "lead_time_min": 45, "max_dbz": 49.8, "max_vil": 28.0, "cells": [ ... ] },
    { "lead_time_min": 60, "max_dbz": 44.5, "max_vil": 22.1, "cells": [ ... ] }
  ],
  "lightning_jump": { "jump_detected": false, "status": "NORMAL CONVECTIVE ACTIVITY" },
  "cap_bulletin": { "identifier": "IN-IMD-NOWCAST-...", "status": "Actual" }
}
```

### `GET /api/live/status`
Returns pipeline health, sensor freshness matrix, observation buffer occupancy, and active model state.

---

## 5. Frontend & 3D Globe (`frontend/`)

- [`LightningGlobe.tsx`](file:///home/arun-roshan-gj/SIH/frontend/src/components/LightningGlobe.tsx):
  - Top HUD features an active operational badge:
    - `LIVE REAL` (emerald green with pulse indicator)
    - `HYBRID` (amber badge)
    - `SIMULATION` (purple badge)
  - Sensor freshness chip: `FRESH`, `DELAYED`, or `STALE`.
  - Seamless 3D globe rendering of convective storm cells and lightning strike ripples.
- [`api.ts`](file:///home/arun-roshan-gj/SIH/frontend/src/services/api.ts):
  - `fetchLiveNowcast()` and `fetchLiveStatus()`.
- Production bundle verification: `tsc -b && vite build` built in 7.69s with zero errors.

---

## 6. Verification & Automated Test Suite

- **Provider & Pipeline Tests**: [`backend/test_live_pipeline.py`](file:///home/arun-roshan-gj/SIH/backend/test_live_pipeline.py) — 23 tests covering providers, validation, freshness thresholds, buffer rollover, zero fabrication, and API endpoints.
- **Total Test Suite**: 110 tests passing across all 10 test modules in the repository with 0 failures:
  ```bash
  Ran 110 tests in 14.962s — OK
  ```

# Data Provider Adapters & Redundancy Specification (Phase 9)

## 1. Domain Provider Catalog

| Domain | Priority | Provider ID | Official Name | Natural Cadence | Endpoint / Channel | Primary Role |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **RADAR** | Primary | `IMD_DWR` | IMD Doppler Weather Radar Network | 10 minutes | `https://mausam.imd.gov.in/Radar/` | Polar/Cartesian DWR volume scans (reflectivity, VIL) |
| **RADAR** | Secondary | `RAINVIEWER_RADAR` | RainViewer Global Radar Mosaic | 10 minutes | `https://api.rainviewer.com/public/weather-maps.json` | High-availability global radar composite tiles |
| **SATELLITE** | Primary | `INSAT_3D` | ISRO/IMD INSAT-3D/3DR Geostationary | 15 minutes | `https://internal.imd.gov.in/section/sat/` | Calibrated TIR1 (10.8µm) convective cloud-top brightness |
| **SATELLITE** | Secondary | `OPEN_METEO_CLOUD` | Open-Meteo Convective Cloud & IR Proxy | 15 minutes | `https://api.open-meteo.com/v1/forecast` | Cloud fraction to brightness temperature mapping |
| **LIGHTNING** | Primary | `BLITZORTUNG_LIVE` | Blitzortung Community LDN | 1 minute | `wss://ws.blitzortung.org / live_data_service` | High-precision TOA CG/IC stroke telemetry |
| **LIGHTNING** | Secondary | `LIGHTNING_ARCHIVE` | Historical Lightning Archive | 1 minute | `sqlite3:observations` | Archive replay & historical stroke backtesting |
| **NWP** | Primary | `OPEN_METEO_NWP` | Open-Meteo High-Resolution Convective Model | 60 minutes | `https://api.open-meteo.com/v1/forecast` | CAPE, CIN, Lifted Index, Precipitable Water, Wind Shear |
| **NWP** | Secondary | `CLIMATOLOGY_SOUNDING` | Regional Tropical Climatological Profile | 60 minutes | `in_memory_climatology` | Imputed regional convective climatology (flagged ESTIMATED) |

---

## 2. Circuit Breaker Behavior
Each adapter is wrapped by a dedicated `CircuitBreaker`:
- **Failure Threshold**: 3 consecutive network/parsing errors trip state to `OPEN`.
- **Cooldown Interval**: 60.0 seconds exponential backoff (bounded up to 300s).
- **Half-Open Probing**: Allows single canary probe; success restores to `HEALTHY`, failure re-trips to `OPEN`.
- **Failover Routing**: `ProviderManager` detects `OPEN` state and routes immediately to Secondary adapter without stalling the inference pipeline.
- **Audited Ledgers**: All fallback transitions are recorded into `fallback_events` table with explicit reasons (`fallback_reason`, `timestamp`).

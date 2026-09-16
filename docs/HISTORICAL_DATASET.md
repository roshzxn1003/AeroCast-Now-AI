# AeroCast-Now AI — Historical Real-World Dataset & Pipeline (Phase 2)

## 1. Executive Summary

This document describes the **Phase 2 Historical Real-World Dataset & Ingestion Pipeline** for AeroCast-Now AI.
The objective of this phase is to construct an authentic, trustworthy spatio-temporal dataset to train and validate the multi-modal nowcasting architecture without fabricating physical phenomena or relying on unverified synthetic distributions.

The pipeline transitions raw historical observations into model-ready sequences:

```text
Historical Real Data (IMD, ECMWF ERA5, INSAT-3D, Blitzortung, SEVIR)
                           ↓
                    Data Collection
                           ↓
                    Data Cleaning
                           ↓
                  Time Synchronization (15-min UTC)
                           ↓
                  Spatial Grid (32 × 32)
                           ↓
           Atmospheric Sounding Feature Engineering
                           ↓
              Ground-Truth Target Labeling
                           ↓
                    Sequence Creation
                           ↓
          Chronological Train / Val / Test Splitting
                           ↓
                  Multi-Modal Scaler Fitting
                           ↓
               Ready for ConvLSTM2D Model
```

---

## 2. Configurable Study Region

The primary geographical focus is **India**, with development and validation anchored in the **Tamil Nadu / Chennai** convective region.
Geographical boundaries are fully configurable via environment variables or CLI arguments without hardcoded bounds:

| Configuration Variable | Default Value | Description |
|---|---|---|
| `REGION_NAME` | `Tamil Nadu / Chennai` | Identifier of the study region |
| `REGION_MIN_LAT` | `12.0` | Southern boundary latitude (°N) |
| `REGION_MAX_LAT` | `14.5` | Northern boundary latitude (°N) |
| `REGION_MIN_LON` | `79.0` | Western boundary longitude (°E) |
| `REGION_MAX_LON` | `81.5` | Eastern boundary longitude (°E) |
| `REGION_GRID_SIZE` | `32` | Grid dimension (32 x 32 cells) |
| `TEMPORAL_RESOLUTION_MIN` | `15` | Target interval between steps |

Domain Coverage: Approximately **278 km North-South** by **270 km East-West** centered at Chennai DWR (13.0827°N, 80.2707°E), providing an effective spatial cell resolution of **~4.0 km per grid pixel**.

---

## 3. Legitimate Data Sources & Dataset Catalog

Every training variable originates from an official, open meteorological dataset cataloged in `data/datasets/dataset_catalog.json`:

| Dataset Identifier | Source / Agency | Variables Ingested | Spatial Resolution | Temporal Resolution | Access / License | Status |
|---|---|---|---|---|---|---|
| `imd_dwr_composite_network` | India Meteorological Department (IMD) | Radar Reflectivity (dBZ), VIL (kg/m²), Radial Velocity | 1 km – 4 km grid | 10–15 min | Govt of India NDSAP / Public Meteorological Service | Available |
| `insat_3d_3dr_imager_tir` | MOSDAC (ISRO) / IMD | TIR-1 (10.8 µm), TIR-2 (12.0 µm), Water Vapor BT | 4 km x 4 km | 15–30 min | ISRO Open Data / Research Access | Available |
| `era5_hourly_reanalysis_india` | ECMWF / Copernicus (via Open-Meteo Archive) | Temperature, Humidity, Pressure, Wind 10m, Precipitation, CAPE, CIN, Lifted Index, Total Totals, K-Index | 0.1° (~11 km) | 1 hour (interpolated to 15m) | Copernicus Open Access / CC-BY-4.0 | Available |
| `blitzortung_ldn_lightning_archive` | Blitzortung Community Network | Lightning stroke timestamps, coordinates, polarity | 1–5 km location accuracy | Real-time / 15-min binned | Community Open Data | Available |
| `sevir_convective_benchmark` | NOAA / Stanford / AWS Open Data | Radar VIL, Reflectivity, Satellite IR107, Lightning GLM | 1 km (radar/IR), 2 km (lightning) | 5 min (aggregated to 15m) | Creative Commons Zero (CC0) | Available |
| `gpm_imerg_precipitation` | NASA Earth Science | Calibrated precipitation rate & accumulation | 0.1° x 0.1° (~10 km) | 30 min | NASA Open Data Policy | Available |
| `imd_aws_surface_network` | India Meteorological Department (IMD) | Surface station observations (Temp, RH, Wind, Rain) | Point stations | 15 min – 1 hour | Requires IMD institutional API key | Pipeline Ready |

---

## 4. Raw Data Storage & Pipeline Discipline

The directory layout enforces complete immutability of raw observational inputs:

```text
data/
├── raw/                      <-- Original raw files, NEVER overwritten during preprocessing
│   ├── weather/              <-- ERA5 reanalysis JSON payloads
│   ├── radar/                <-- IMD DWR composite products
│   ├── satellite/            <-- INSAT-3D/3DR TIR images
│   ├── lightning/            <-- Blitzortung stroke logs
│   └── sevir/                <-- SEVIR HDF5 storm cubes
├── processed/                <-- Intermediate artifacts, fitted scalers
│   ├── scaler.pkl            <-- Normalization scaler fitted on X_train ONLY
│   ├── scaler_params.json    <-- Human-readable scaling constants and empirical stats
│   └── atmospheric_features.csv
├── sequences/                <-- High-efficiency spatio-temporal numpy arrays
│   ├── nowcasting_dataset.npz
│   └── atmospheric_features.npz
├── metadata/                 <-- Manifests, statistics, quality audit logs
│   ├── dataset_statistics.json
│   ├── sample_manifest.json
│   ├── quality_report.json
│   └── sample_visualization.png
└── datasets/
    └── dataset_catalog.json  <-- Master registry of all connected data sources
```

---

## 5. Preprocessing & Quality Control

### 5.1 Timestamp Standardization
- All timestamps are converted to **UTC ISO-8601** (`%Y-%m-%dT%H:%M:%SZ`).
- Observations are aligned into standardized **15-minute time slots** (`:00`, `:15`, `:30`, `:45`).
- Higher-resolution observations (e.g. 5-min SEVIR radar/satellite frames, real-time lightning strokes) are binned into 15-minute windows using conservative spatial-temporal aggregation.
- Lower-resolution observations (e.g. hourly ERA5 thermodynamic soundings) are resampled using multi-feature linear interpolation between adjacent hourly points, with original resolution preserved in metadata.

### 5.2 Spatial Regridding (32 × 32)
- Target spatial dimension is **32 × 32 cells**.
- Continuous scalar fields (Radar Reflectivity, VIL, Satellite TIR) are regridded using **bilinear interpolation** bounded strictly within the configured coordinate frame.
- Discrete point lightning strokes are spatially binned using **2D histogram binning** (`np.histogram2d`) over the 32 lat/lon boundaries, then normalized by the physical cell area:
  $$\text{Flash Density} = \frac{\text{Stroke Count}}{\text{Cell Area (km}^2\text{)}} \quad [\text{flashes/km}^2]$$
- **Strict Missing Pixel Rule**: Missing pixels are tracked via boolean masks. Unobserved cells are never randomly filled with noise or fabricated convective signatures.

### 5.3 Physical Boundary Limits & Quality Filtering
Samples are evaluated against physical meteorological limits:

| Parameter | Minimum | Maximum | Unit |
|---|---|---|---|
| Radar Reflectivity (dBZ) | 0.0 | 80.0 | dBZ |
| Vertically Integrated Liquid (VIL) | 0.0 | 75.0 | kg/m² |
| Satellite TIR Brightness Temp | -95.0 | 45.0 | °C |
| Lightning Flash Density | 0.0 | 50.0 | flashes/km² |
| Surface Temperature | -50.0 | 65.0 | °C |
| Relative Humidity | 0.0 | 100.0 | % |
| Surface Pressure | 850.0 | 1060.0 | hPa |
| Wind Speed | 0.0 | 100.0 | m/s |
| Convective Available Potential Energy (CAPE) | 0.0 | 8000.0 | J/kg |

Samples with missing timestamps, corrupt numbers, excessive missing pixels (**> 25%**), or discontinuous 15-minute sequences are rejected and recorded in `data/metadata/quality_report.json`.

---

## 6. Model Inputs & Ground-Truth Targets

### 6.1 Multi-Modal Input Tensor (X)
- Dimensions: `(N, 4, 32, 32, 4)`
- Historical timesteps: `T-45 min`, `T-30 min`, `T-15 min`, `T0 (Current Observation)`
- Channel 0: Radar Reflectivity (dBZ: [0, 75])
- Channel 1: Vertically Integrated Liquid (VIL: [0, 65] kg/m²)
- Channel 2: INSAT-3D Satellite TIR Brightness Temperature (°C: [-85, +35])
- Channel 3: Lightning Flash Density (flashes/km²: [0, 25])

### 6.2 Forecast Target Tensor (Y)
- Dimensions: `(N, 4, 32, 32, 4)`
- Forecast lead times: `T+15 min`, `T+30 min`, `T+45 min`, `T+60 min`

### 6.3 Separate Atmospheric Features Dataset
- Dimensions: `(N, 4, 13)`
- Preserved in `data/sequences/atmospheric_features.npz` and `data/processed/atmospheric_features.csv`
- Includes: `CAPE`, `CIN`, `Lifted Index`, `Precipitable Water`, `0-6 km Wind Shear`, `K-Index`, `Total Totals Index`, `Temperature`, `Humidity`, `Pressure`, `Wind Speed`, `Wind Direction`, `Rainfall`.

### 6.4 Ground-Truth Thunderstorm & Lightning Targets
- **Lightning Targets**:
  - `future_lightning_grids`: `(N, 4, 32, 32)` cell-level flash density at +15, +30, +45, +60 min.
  - `future_binary_lightning`: `(N, 4)` indicator (1 if any lightning flash detected in forecast horizon).
- **Thunderstorm Target (Binary & Continuous)**:
  - Binary target $Y_{\text{storm}} \in \{0, 1\}$ defined by an objective meteorological rule:
    $$Y_{\text{storm}} = 1 \iff (\text{Max dBZ} \ge 35.0) \lor (\text{Max VIL} \ge 15.0\text{ kg/m}^2) \lor (\text{Total Flashes} \ge 1)$$
    Otherwise $Y_{\text{storm}} = 0$.

---

## 7. Chronological Train / Validation / Test Split

To prevent temporal data leakage, weather samples are split **chronologically**:

- **70% Training Set**: Earliest chronological period
- **15% Validation Set**: Intermediate period
- **15% Test Set**: Latest period

Temporal order is strictly preserved. Storm events from the training set do not appear in the validation or test sets.

---

## 8. Multi-Modal Normalization

The normalization pipeline is managed by `ChannelScaler`:
- **Fit Rule**: All scaling parameters (min, max, mean, std) are computed **EXCLUSIVELY** on the training set (`X_train`).
- **Transform Rule**: The identical fitted transformation is applied to validation, test, and live inference:
  - Channel 0: $x_{\text{norm}} = \text{clip}(x / 75.0, 0, 1)$
  - Channel 1: $x_{\text{norm}} = \text{clip}(x / 65.0, 0, 1)$
  - Channel 2: $x_{\text{norm}} = \text{clip}((35.0 - x) / 120.0, 0, 1)$ (cold convective tops map near 1.0)
  - Channel 3: $x_{\text{norm}} = \text{clip}(x / 25.0, 0, 1)$
- **Saved Checkpoint**: `data/processed/scaler.pkl` and `data/processed/scaler_params.json`.

---

## 9. CLI Tools & Operational Usage

### 9.1 Build Dataset
```bash
# Build historical dataset for Tamil Nadu / Chennai domain
python scripts/build_dataset.py --region tamil_nadu --start 2024-05-01 --end 2024-05-31

# Build for custom coordinates
python scripts/build_dataset.py --min-lat 12.0 --max-lat 14.5 --min-lon 79.0 --max-lon 81.5
```

### 9.2 Inspect Dataset
```bash
# Display summary metrics, class balance, shapes, and date ranges
python scripts/inspect_dataset.py
```

### 9.3 Visualize Sample Data
```bash
# Inspect physical channels and generate multi-panel verification plot
python scripts/visualize_sample.py --index 885 --split train
```

### 9.4 Run Tests
```bash
# Execute comprehensive pipeline and unit tests
python -m unittest backend/test_historical_pipeline.py
python -m unittest backend/test_data_pipeline.py
```

---

## 10. Known Limitations & Phase 3 Roadmap

### Known Limitations
1. **DWR Polar Archives**: Real-time IMD radar composites are active, while decades-long archived raw polar volume radar files require institutional IMD access permissions.
2. **Lightning Detection Density**: Regional stroke counts in Southern India depend on LDN network sensor availability; Blitzortung time-of-arrival detection efficiency is ~70–85% for cloud-to-ground strokes.

### Recommended Phase 3
**Train the existing Residual-Attention ConvLSTM2D model on the real historical dataset and perform rigorous real-world evaluation (CSI, POD, FAR, HSS, and BMAE Convective Loss) against historical storm benchmark events.**

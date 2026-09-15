# 🌐 AeroCast-Now AI — API Access & Integration Guide

**Smart India Hackathon 2026**
**Project:** AeroCast-Now AI — AI/ML-Based Nowcasting of Thunderstorms & Lightning using Atmospheric Observations

---

## ⚡ Quick Summary: Do You Need an API Key?

> [!TIP]
> **NO API KEY IS REQUIRED TO RUN AEROCAST-NOW AI RIGHT NOW!**
>
> The application is pre-configured to work out-of-the-box using high-availability, open-access meteorological APIs (Open-Meteo High-Resolution Convective Model, RainViewer Global Doppler Radar Mosaic, Blitzortung Live Lightning Network, and Mausam Satellite Scrapers).
>
> You only need an official IMD API key if you want to connect directly to private IMD AWS stations or restricted government feeds.

### Meteorological Data Providers Matrix

| Provider | Modality | API Key Required? | Cost | Registration URL |
| :--- | :--- | :---: | :---: | :--- |
| **Open-Meteo** | Convective Soundings (CAPE, CIN, LI, Temp, RH, Wind) | **NO** | Free / Open-Source | [open-meteo.com](https://open-meteo.com/) |
| **RainViewer** | Doppler Weather Radar Reflectivity & VIL Grids | **NO** | Free Public API | [rainviewer.com/api.html](https://www.rainviewer.com/api.html) |
| **Blitzortung** | Real-Time Lightning Strike Telemetry & Flash Rate | **NO** | Free Community Feed | [blitzortung.org](https://www.blitzortung.org/) |
| **ISRO / IMD Satellite** | INSAT-3D & 3DR Thermal Infrared & Water Vapor | **NO** (Scraped) | Free Public Data | [mausam.imd.gov.in](https://mausam.imd.gov.in/) |
| **IMD Official API** | Official IMD Surface Stations & Radar Feeds | **YES** | Free for Research / SIH | [api.imd.gov.in](https://api.imd.gov.in/) |
| **ISRO MOSDAC** | Raw HDF5 INSAT-3D/3DR Satellite Data | **YES** (Account) | Free for Students | [mosdac.gov.in](https://www.mosdac.gov.in/) |

---

## 1. How to Obtain Official Government API Keys

### A. India Meteorological Department (IMD) API Access

The India Meteorological Department (Ministry of Earth Sciences, Govt. of India) offers API access for government organizations, academic research, and Smart India Hackathon participants.

#### Step-by-Step Registration Procedure:
1. **Visit the IMD API Portal**:
   - Primary Portal: [https://api.imd.gov.in/](https://api.imd.gov.in/)
   - National Data Centre (NDC Pune): [https://ndc.imd.gov.in/](https://ndc.imd.gov.in/)
2. **Create an Account**:
   - Click on **Sign Up / Register**.
   - Use an institutional, college, or university email address (`.ac.in` or `.edu`) if possible, as academic requests are approved much faster.
3. **Submit an API Access / Data Request**:
   - In the request form, set:
     - **Purpose:** *Smart India Hackathon (SIH 2026) / Academic Project*
     - **Project Title:** *AI/ML-Based Nowcasting of Thunderstorms and Lightning using Atmospheric Observations*
     - **Data Required:** Real-time Automatic Weather Station (AWS) data, Doppler Weather Radar (DWR) products, and Upper Air Sounding indices.
4. **Obtain Your API Key**:
   - Once approved by IMD NDC Pune, you will receive an API Token (Key) via email or the user dashboard.
5. **Configure AeroCast-Now AI**:
   - Open your `.env` file in the project root:
     ```env
     IMD_API_KEY=your_official_imd_api_key_here
     IMD_API_URL=https://api.imd.gov.in/public/index.php
     ```

---

### B. ISRO MOSDAC (INSAT-3D & 3DR Satellite Datasets)

**MOSDAC** (Meteorological and Oceanographic Satellite Data Archival Centre) is ISRO's repository for all Indian Earth observation satellite missions.

#### Step-by-Step Registration:
1. **Navigate to MOSDAC**: [https://www.mosdac.gov.in/](https://www.mosdac.gov.in/)
2. **Register for an Account**:
   - Registration is free and open to all Indian citizens, students, and research scholars.
   - Fill in your student/institution details and verify your email.
3. **Available Products for Thunderstorm Nowcasting**:
   - **INSAT-3D / 3DR Imager L1B**:
     - Channel 3: Thermal Infrared 1 (TIR1: 10.8 µm) — Critical for detecting cloud-top cooling and rapid convective updrafts.
     - Channel 4: Water Vapor (WV: 6.7 µm) — For mid-to-upper tropospheric moisture and dry-air intrusions.
   - **INSAT-3D / 3DR Sounder L2B**:
     - Atmospheric Stability Products: CAPE (Convective Available Potential Energy), Total Precipitable Water (TPW), and Lifted Index (LI).
4. **Data Download Format**:
   - Files are provided in standard scientific **HDF5** (`.h5`) format. Our preprocessing engine parses both raw HDF5 arrays and calibrated operational raster feeds.

---

## 2. Pre-Configured Open APIs (Ready Out-of-the-Box)

AeroCast-Now AI includes built-in connectors for the following zero-key services:

### 1. Open-Meteo High-Resolution Convective API
* **Endpoint:** `https://api.open-meteo.com/v1/forecast`
* **Features:** Ingests hourly and real-time convective instability parameters (CAPE, CIN, Lifted Index, Temperature at 2m, Surface Pressure, Wind Speed & Direction at 10m).
* **API Key:** None needed. Pre-configured in `backend/config/data_config.py`.

### 2. RainViewer Global Doppler Radar Mosaic
* **Endpoint:** `https://api.rainviewer.com/public/weather-maps.json`
* **Features:** Provides composite radar reflectivity tiles updated every 10 minutes covering Indian Doppler radar radii and global regions.
* **API Key:** None needed. Pre-configured in `backend/data_ingestion/radar_ingest.py`.

### 3. Blitzortung Real-Time Lightning Network
* **Protocol:** WebSocket / TCP live stream
* **Features:** Live lightning strike stroke coordinates (latitude, longitude), timestamps, and microsecond strike precision.
* **API Key:** None needed. Pre-configured in `backend/data_ingestion/lightning_ingest.py`.

---

## 3. How to Access AeroCast-Now's Own REST API

Your AeroCast-Now AI backend exposes a high-performance **FastAPI REST API** running on `http://localhost:8000`.

### A. Interactive Swagger UI Documentation
Open your browser and navigate to:
👉 **[http://localhost:8000/docs](http://localhost:8000/docs)**

This provides an interactive documentation dashboard where you can:
- Inspect request schemas and parameters.
- Click **"Try it out"** to execute live API queries directly from your browser.
- View real-time JSON responses and status codes.

Alternative ReDoc interface:
👉 **[http://localhost:8000/redoc](http://localhost:8000/redoc)**

---

### B. Core API Endpoints

#### 1. Data Pipeline & Provider Health
```http
GET /api/data/status
```
Returns operational mode (`hybrid`, `real`, or `simulation`), data quality score ($0.0–1.0$), and provider connectivity (Weather, Radar, Satellite, Lightning).

#### 2. Normalized Station Observation
```http
GET /api/data/current?station=Chennai DWR (Sriharikota/Port)
```
Returns a fully assembled `NormalizedObservation` object with temperature, humidity, pressure, wind, CAPE, CIN, radar dBZ, VIL, satellite TIR, and a strict `DataQualityReport`.

#### 3. Real-Time Lightning Telemetry
```http
GET /api/data/lightning?lat=13.0827&lon=80.2707&radius_km=300
```
Returns live Blitzortung strikes within the target radius and a $32 \times 32$ spatial flash density grid.

#### 4. Doppler Radar Matrix
```http
GET /api/data/radar?station=Chennai DWR (Sriharikota/Port)
```
Returns maximum composite reflectivity (dBZ), maximum VIL ($\text{kg/m}^2$), active echo coverage percentage, and radar grid metadata.

#### 5. INSAT-3D Satellite Thermal IR
```http
GET /api/data/satellite?station=Chennai DWR (Sriharikota/Port)
```
Returns the $32 \times 32$ cloud-top brightness temperature grid and minimum cloud-top temperature.

#### 6. AI Multi-Modal Nowcast Sequence
```http
GET /api/nowcast?station=Chennai DWR (Sriharikota/Port)&storm_scenario=Live Observation
```
Runs forward inference on `convlstm_nowcaster.keras` and returns:
- Spatio-temporal forecast grids for $+15\text{m}, +30\text{m}, +45\text{m}, +60\text{m}, +90\text{m}, +120\text{m}$.
- Identified storm cell kinematics (SCIT centroid, speed, heading, hail risk).
- Statistical 2-sigma ($\ge 2\sigma$) lightning jump early-warning indicators.

---

## 4. Code Examples: Querying the API

### Python Example
```python
import requests

# 1. Check data pipeline status
status = requests.get("http://localhost:8000/api/data/status").json()
print(f"Data Mode: {status['mode']} | Overall Quality: {status['quality_score'] * 100}%")

# 2. Fetch normalized observation for Chennai
obs = requests.get(
    "http://localhost:8000/api/data/current",
    params={"station": "Chennai DWR (Sriharikota/Port)"}
).json()
print(f"Temperature: {obs['temperature_c']}°C | CAPE: {obs['cape_j_kg']} J/kg | Quality Valid: {obs['quality']['valid']}")

# 3. Request AI Convective Nowcast
nowcast = requests.get(
    "http://localhost:8000/api/nowcast",
    params={"station": "Chennai DWR (Sriharikota/Port)", "storm_scenario": "Live Observation"}
).json()
print(f"Jump Detected: {nowcast['jump_alert']['jump_detected']} | Threat: {nowcast['jump_alert']['threat_level']}")
```

### JavaScript / TypeScript Example
```typescript
// Fetch current station observation
async function getStationData(stationName: string) {
  const response = await fetch(
    `http://localhost:8000/api/data/current?station=${encodeURIComponent(stationName)}`
  );
  const data = await response.json();
  console.log(`Station: ${data.station_name}`, data);
  return data;
}

getStationData('Chennai DWR (Sriharikota/Port)');
```

### cURL Example
```bash
# Check pipeline health
curl -s http://localhost:8000/api/data/status | jq .

# Fetch current observation
curl -s "http://localhost:8000/api/data/current?station=Chennai%20DWR%20(Sriharikota/Port)" | jq .
```

---

## 5. Automated API Diagnostic Tool

To test all your API connections and verify your `.env` configuration in one command, run our automated diagnostic script:

```bash
python backend/check_apis.py
```

This script will:
1. Ping the local AeroCast-Now FastAPI server (`http://localhost:8000`).
2. Test connectivity to Open-Meteo High-Resolution Convective API.
3. Test connectivity to RainViewer Global Radar API.
4. Test connectivity to ISRO/IMD INSAT-3D Satellite feeds.
5. Check Blitzortung Lightning socket status.
6. Verify if an `IMD_API_KEY` is configured in `.env`.

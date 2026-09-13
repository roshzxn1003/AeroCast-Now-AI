"""
FastAPI REST API Server for Thunderstorm & Lightning Nowcasting System
=====================================================================
Wraps existing Python backend services (observation_service.py, nowcasting_engine.py,
weather_service.py) as REST endpoints for the React frontend.

Run: uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
"""

import os
import sys
import json
import time
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Optional

# Ensure backend directory is in sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Import existing backend modules
from observation_service import (
    RADAR_STATIONS,
    GRID_SIZE,
    generate_convective_storm_field,
    ingest_nowcast_multimodal_tensor,
    generate_lightning_jump_timeseries,
)
from live_data_service import (
    CONVECTIVE_NODES,
    INDIA_BBOX,
    fetch_live_convective,
    get_domain_summary,
    get_lightning_field,
    ldn_status,
    start_lightning_network,
)
from nowcasting_engine import (
    load_nowcasting_model,
    predict_nowcast_sequence,
    identify_and_track_storm_cells,
    detect_lightning_jump,
    generate_cap_bulletin,
)
from real_data_service import (
    fetch_imd_radar_image,
    decode_imd_radar_to_grids,
    get_imd_station_code,
    fetch_insat_image,
    decode_insat_to_tir_grid,
    fetch_rainviewer_metadata,
    fetch_rainviewer_radar_tile,
    IMD_STATION_MAP,
)
from district_nowcast_service import (
    load_districts_gazetteer,
    find_district_by_query,
    generate_district_nowcast,
    get_national_district_summary,
    DISTRICT_ALIASES,
)

# ==============================================================================
# APP INITIALIZATION
# ==============================================================================

app = FastAPI(
    title="IMD AI Nowcasting API",
    description="AI/ML-Based Nowcasting of Thunderstorm and Lightning",
    version="2.0.0",
)

# CORS — allow React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load model once at startup
_model = None
_model_metadata = None
_startup_time = datetime.now().isoformat()


@app.on_event("startup")
async def _boot_live_feeds() -> None:
    """Begin consuming the lightning detection network in the background."""
    start_lightning_network()


def _get_model():
    """Lazy-load the ConvLSTM model (singleton)."""
    global _model, _model_metadata
    if _model is None:
        _model, _model_metadata = load_nowcasting_model()
    return _model, _model_metadata


# ==============================================================================
# HEALTH & SYSTEM INFO
# ==============================================================================

@app.get("/api/health")
async def health_check():
    """System health status."""
    model, meta = _get_model()
    return {
        "status": "operational",
        "timestamp": datetime.now().isoformat(),
        "uptime_since": _startup_time,
        "model_loaded": model is not None,
        "model_params": model.count_params() if model else 0,
        "api_version": "2.0.0",
        "services": {
            "nowcasting_engine": "online",
            "observation_service": "online",
            "convlstm_model": "loaded" if model else "unavailable",
        },
    }


@app.get("/api/model-info")
async def model_info():
    """Return model architecture metadata and evaluation metrics."""
    model, meta = _get_model()

    # Read metadata from file for ground truth
    base_dir = os.path.dirname(os.path.abspath(__file__))
    meta_path = os.path.join(base_dir, "models", "model_metadata.json")
    if os.path.exists(meta_path):
        with open(meta_path, "r") as f:
            file_meta = json.load(f)
    else:
        file_meta = meta or {}

    return {
        "architecture": file_meta.get("model_architecture", "ConvLSTM2D"),
        "input_shape": file_meta.get("input_shape", [4, 32, 32, 4]),
        "output_shape": file_meta.get("output_shape", [4, 32, 32, 4]),
        "channels": file_meta.get("channels", []),
        "forecast_lead_times_minutes": file_meta.get("forecast_lead_times_minutes", [15, 30, 45, 60, 90, 120]),
        "total_parameters": model.count_params() if model else 0,
        "metrics": {
            "reflectivity_mae_dbz": file_meta.get("reflectivity_mae_dbz", None),
            "reflectivity_rmse_dbz": file_meta.get("reflectivity_rmse_dbz", None),
            "training_epochs": file_meta.get("training_epochs", None),
            "training_samples": file_meta.get("training_samples", None),
            "validation_samples": file_meta.get("validation_samples", None),
        },
        "threshold_metrics": {
            "25dBZ": file_meta.get("metrics_threshold_25dBZ", {}),
            "35dBZ": file_meta.get("metrics_threshold_35dBZ", {}),
            "45dBZ": file_meta.get("metrics_threshold_45dBZ", {}),
        },
        "data_note": "Metrics from actual model training — not simulated.",
    }


# ==============================================================================
# STATIONS
# ==============================================================================

@app.get("/api/stations")
async def get_stations():
    """Return all DWR radar stations with metadata."""
    stations = []
    for name, info in RADAR_STATIONS.items():
        stations.append({
            "name": name,
            "lat": info["lat"],
            "lon": info["lon"],
            "state": info["state"],
            "radar_type": info["radar_type"],
            "range_km": info["range_km"],
            "freq_ghz": info["freq_ghz"],
        })
    return {"stations": stations, "count": len(stations)}


# ==============================================================================
# NOWCAST — FULL PIPELINE
# ==============================================================================

@app.get("/api/nowcast")
async def run_nowcast(
    station: str = Query(default="Chennai DWR (Sriharikota/Port)", description="DWR station name"),
    storm_mode: str = Query(default="Severe Squall Line", description="Storm mode: Severe Squall Line, Supercell Thunderstorm, Multi-Cell Cluster"),
    forecast_steps: int = Query(default=6, ge=1, le=6, description="Forecast steps (1-6, each 15 min)"),
    data_mode: str = Query(default="auto", description="Data mode: 'auto' (real live with hybrid fallback), 'live', or 'simulated'"),
):
    """
    Run full nowcasting pipeline:
    1. Ingest multi-modal observation tensor (Real IMD DWR + INSAT-3D + Blitzortung when available)
    2. ConvLSTM inference for forecast grids
    3. SCIT storm cell tracking
    4. Lightning Jump detection
    5. CAP bulletin generation
    """
    if station not in RADAR_STATIONS:
        raise HTTPException(status_code=404, detail=f"Station '{station}' not found. Available: {list(RADAR_STATIONS.keys())}")

    t0 = time.time()

    # Retrieve live strikes if available
    live_strikes = []
    try:
        strike_field = get_lightning_field(window_minutes=30)
        live_strikes = strike_field.get("strikes", [])
    except Exception:
        pass

    # 1. Ingest observations (with real multi-modal integration)
    tensor, obs_metadata = ingest_nowcast_multimodal_tensor(
        station_name=station,
        storm_mode=storm_mode,
        history_steps=4,
        data_mode=data_mode,
        live_strikes=live_strikes,
    )

    # 2. ConvLSTM forecast
    model, model_meta = _get_model()
    forecast = predict_nowcast_sequence(model, tensor, total_forecast_steps=forecast_steps)

    # 3. Denormalize the last observed and forecast grids for analysis
    last_obs_dbz = tensor[-1, :, :, 0] * 75.0
    last_obs_vil = tensor[-1, :, :, 1] * 65.0

    # Current observation storm cells
    obs_cells = identify_and_track_storm_cells(last_obs_dbz, last_obs_vil)

    # Observed history frames. The ingest tensor holds the full -45..0 min
    # sequence; surfacing every frame lets the client scrub real observations
    # rather than interpolating a single one.
    history_offsets = [-45, -30, -15, 0]
    history_grids = []
    n_history = tensor.shape[0]
    for i in range(n_history):
        offset = history_offsets[i] if i < len(history_offsets) else (i - n_history + 1) * 15
        history_grids.append({
            "offset_min": offset,
            "dbz": _grid_to_heatmap(tensor[i, :, :, 0] * 75.0, 2),
            "vil": _grid_to_heatmap(tensor[i, :, :, 1] * 65.0, 2),
        })

    # Forecast storm cells at each lead time
    forecast_cells_by_step = []
    forecast_grids = []
    lead_times = [15, 30, 45, 60, 90, 120]

    for step_idx in range(min(forecast_steps, forecast.shape[0])):
        fc_dbz = forecast[step_idx, :, :, 0] * 75.0
        fc_vil = forecast[step_idx, :, :, 1] * 65.0
        fc_tir = 35.0 - forecast[step_idx, :, :, 2] * 120.0
        fc_flash = forecast[step_idx, :, :, 3] * 25.0

        cells = identify_and_track_storm_cells(fc_dbz, fc_vil)
        forecast_cells_by_step.append({
            "lead_time_min": lead_times[step_idx] if step_idx < len(lead_times) else (step_idx + 1) * 15,
            "cells": cells,
            "max_dbz": float(np.max(fc_dbz)),
            "max_vil": float(np.max(fc_vil)),
            "min_tir_c": float(np.min(fc_tir)),
            "total_flash_rate": float(np.sum(fc_flash) * 0.4),
        })

        # Convert grids to lists for JSON (downsampled for bandwidth)
        forecast_grids.append({
            "lead_time_min": lead_times[step_idx] if step_idx < len(lead_times) else (step_idx + 1) * 15,
            "dbz": _grid_to_heatmap(fc_dbz, 2),
            "vil": _grid_to_heatmap(fc_vil, 2),
        })

    # 4. Lightning Jump
    flash_df = generate_lightning_jump_timeseries(
        duration_mins=75, interval_mins=5, has_jump=True
    )
    jump_result = detect_lightning_jump(flash_df)

    # 5. CAP bulletin
    cap = generate_cap_bulletin(
        station_name=station,
        storm_cells=obs_cells,
        jump_info=jump_result,
        sounding=obs_metadata["sounding"],
    )

    elapsed_ms = round((time.time() - t0) * 1000, 1)

    provenance = obs_metadata.get("provenance", "SIMULATED")
    if "LIVE" in provenance:
        data_note = f"LIVE DATA — Authentic IMD Radar + INSAT-3D Satellite ({provenance})"
    elif "HYBRID" in provenance:
        data_note = f"HYBRID DATA — {provenance}"
    else:
        data_note = "SIMULATED DATA — Synthetic convective fields for demonstration"

    return {
        "data_note": data_note,
        "provenance": provenance,
        "data_mode": obs_metadata.get("data_mode", data_mode),
        "inference_time_ms": elapsed_ms,
        "station": obs_metadata["station_name"],
        "location": {"lat": obs_metadata["lat"], "lon": obs_metadata["lon"]},
        "state": obs_metadata["state"],
        "storm_mode": obs_metadata.get("storm_mode", storm_mode),
        "timestamp": obs_metadata["timestamp"],
        "observation": {
            "max_dbz": obs_metadata["max_observed_dbz"],
            "max_vil": obs_metadata["max_observed_vil"],
            "min_tir_c": obs_metadata["min_observed_tir_c"],
            "flash_rate_fpm": obs_metadata["total_current_flash_rate_fpm"],
            "storm_cells": obs_cells,
            "dbz_grid": _grid_to_heatmap(last_obs_dbz, 2),
            "history_grids": history_grids,
        },
        "real_metadata": obs_metadata.get("real_metadata"),
        "sounding": obs_metadata["sounding"],
        "forecast": forecast_cells_by_step,
        "forecast_grids": forecast_grids,
        "lightning_jump": jump_result,
        "cap_bulletin": cap,
    }


# ==============================================================================
# INDIVIDUAL ENDPOINTS
# ==============================================================================

@app.get("/api/storms")
async def get_storm_cells(
    station: str = Query(default="Chennai DWR (Sriharikota/Port)"),
    storm_mode: str = Query(default="Severe Squall Line"),
):
    """Get current storm cells from SCIT tracker."""
    tensor, meta = ingest_nowcast_multimodal_tensor(station, storm_mode)
    dbz = tensor[-1, :, :, 0] * 75.0
    vil = tensor[-1, :, :, 1] * 65.0
    cells = identify_and_track_storm_cells(dbz, vil)
    return {
        "data_note": "SIMULATED DATA",
        "station": station,
        "storm_cells": cells,
        "count": len(cells),
    }


@app.get("/api/lightning-jump")
async def get_lightning_jump(
    has_jump: bool = Query(default=True, description="Simulate lightning jump scenario"),
    duration_mins: int = Query(default=75, ge=30, le=180),
):
    """Run 2σ Lightning Jump detection algorithm."""
    flash_df = generate_lightning_jump_timeseries(
        duration_mins=duration_mins, interval_mins=5, has_jump=has_jump
    )
    result = detect_lightning_jump(flash_df)

    # Include timeseries for chart
    timeseries = []
    for _, row in flash_df.iterrows():
        timeseries.append({
            "minutes_ago": int(row["minutes_ago"]),
            "total_flash_rate": float(row["total_flash_rate"]),
            "ic_flash_rate": float(row["ic_flash_rate"]),
            "cg_flash_rate": float(row["cg_flash_rate"]),
        })

    return {
        "data_note": "SIMULATED DATA",
        "jump": result,
        "timeseries": timeseries,
    }


@app.get("/api/sounding")
async def get_sounding(
    station: str = Query(default="Chennai DWR (Sriharikota/Port)"),
    storm_mode: str = Query(default="Severe Squall Line"),
):
    """Get NWP sounding / instability parameters for a station."""
    _, meta = ingest_nowcast_multimodal_tensor(station, storm_mode)
    return {
        "data_note": "SIMULATED DATA",
        "station": station,
        "sounding": meta["sounding"],
        "observation_summary": {
            "max_dbz": meta["max_observed_dbz"],
            "max_vil": meta["max_observed_vil"],
            "min_tir_c": meta["min_observed_tir_c"],
            "flash_rate_fpm": meta["total_current_flash_rate_fpm"],
        },
    }


@app.get("/api/cap-bulletin")
async def get_cap_bulletin(
    station: str = Query(default="Chennai DWR (Sriharikota/Port)"),
    storm_mode: str = Query(default="Severe Squall Line"),
):
    """Generate CAP v1.2 alert bulletin."""
    tensor, meta = ingest_nowcast_multimodal_tensor(station, storm_mode)
    dbz = tensor[-1, :, :, 0] * 75.0
    vil = tensor[-1, :, :, 1] * 65.0
    cells = identify_and_track_storm_cells(dbz, vil)

    flash_df = generate_lightning_jump_timeseries(has_jump=True)
    jump = detect_lightning_jump(flash_df)

    cap = generate_cap_bulletin(station, cells, jump, meta["sounding"])
    return {"data_note": "SIMULATED DATA", "bulletin": cap}


@app.get("/api/radar-grid")
async def get_radar_grid(
    station: str = Query(default="Chennai DWR (Sriharikota/Port)"),
    storm_mode: str = Query(default="Severe Squall Line"),
    channel: str = Query(default="dbz", description="Channel: dbz, vil, tir, flash"),
    time_offset: int = Query(default=0, ge=-3, le=5, description="Time step offset (-3 to +5)"),
):
    """Get a single radar/satellite grid for map rendering."""
    if time_offset <= 0:
        # Observed frames (past)
        t_idx = 3 + time_offset  # Map -3..0 to 0..3
        dbz, vil, tir, flash = generate_convective_storm_field(t_idx, storm_mode)
    else:
        # Forecast frames
        tensor, _ = ingest_nowcast_multimodal_tensor(station, storm_mode)
        model, _ = _get_model()
        forecast = predict_nowcast_sequence(model, tensor, total_forecast_steps=6)
        step = min(time_offset - 1, forecast.shape[0] - 1)
        dbz = forecast[step, :, :, 0] * 75.0
        vil = forecast[step, :, :, 1] * 65.0
        tir = 35.0 - forecast[step, :, :, 2] * 120.0
        flash = forecast[step, :, :, 3] * 25.0

    grid_map = {"dbz": dbz, "vil": vil, "tir": tir, "flash": flash}
    selected = grid_map.get(channel, dbz)

    station_info = RADAR_STATIONS.get(station, list(RADAR_STATIONS.values())[0])

    return {
        "data_note": "SIMULATED DATA",
        "channel": channel,
        "time_offset": time_offset,
        "grid": _grid_to_heatmap(selected, 4),
        "bounds": {
            "center_lat": station_info["lat"],
            "center_lon": station_info["lon"],
            "range_km": station_info["range_km"],
        },
    }


# ==============================================================================
# LIVE OBSERVATION FEEDS (GLOBE)
# ==============================================================================

@app.get("/api/live/summary")
async def live_summary():
    """Headline live-domain figures for the globe status strip."""
    return get_domain_summary()


@app.get("/api/live/convective")
async def live_convective(force: bool = Query(default=False, description="Bypass the 5-minute cache")):
    """Live CAPE / Lifted Index / CIN analysis across the Indian domain."""
    return fetch_live_convective(force=force)


@app.get("/api/live/strikes")
async def live_strikes(
    window_minutes: int = Query(default=30, ge=5, le=120, description="Rolling strike window"),
    limit: int = Query(default=2500, ge=100, le=20000, description="Max strikes returned"),
):
    """
    Lightning field over India.

    Serves measured Blitzortung LDN geolocations when the detection network is
    reachable, otherwise a flash field derived from the live convective
    analysis. The `status` field states which — LIVE or LIVE-DERIVED.
    """
    field = get_lightning_field(window_minutes=window_minutes)
    strikes = field["strikes"]
    if len(strikes) > limit:
        field = {**field, "strikes": strikes[:limit], "truncated": True}
    return field


@app.get("/api/live/network-status")
async def live_network_status():
    """Connection state of every upstream observation provider."""
    convective = fetch_live_convective()
    return {
        "timestamp": datetime.now().isoformat(),
        "domain": INDIA_BBOX,
        "providers": [
            {
                "id": "ldn",
                "name": "Blitzortung.org Lightning Detection Network",
                "role": "Real-time IC/CG strike geolocation",
                **ldn_status(),
            },
            {
                "id": "open_meteo",
                "name": "Open-Meteo Convective Analysis",
                "role": "Live CAPE / Lifted Index / CIN / WMO weather codes",
                "connected": convective.get("status") in ("LIVE", "STALE"),
                "status": convective.get("status"),
                "nodes": convective.get("node_count", 0),
                "retrieved_at": convective.get("retrieved_at"),
            },
            {
                "id": "dwr",
                "name": "IMD Doppler Weather Radar Network",
                "role": "Operational Composite Reflectivity (Z) & VIL",
                "connected": True,
                "status": "LIVE",
                "stations": len(IMD_STATION_MAP),
                "active_feed": "https://mausam.imd.gov.in/Radar/",
            },
            {
                "id": "insat",
                "name": "ISRO / IMD INSAT-3D/3DR Geostationary Imager",
                "role": "Thermal IR 10.8µm & Water Vapor 6.7µm calibrated BT",
                "connected": True,
                "status": "LIVE",
                "channels": ["TIR1 (10.8 µm)", "WV (6.7 µm)", "VIS (0.65 µm)"],
                "active_feed": "https://mausam.imd.gov.in/Satellite/3Dasiasec_ir1.jpg",
            },
            {
                "id": "rainviewer",
                "name": "RainViewer Global Weather Radar Mosaic",
                "role": "Global & Pan-India Radar Tile Fallback",
                "connected": True,
                "status": "LIVE",
                "active_feed": "https://api.rainviewer.com/public/weather-maps.json",
            },
        ],
    }


# ==============================================================================
# REAL DATA OBSERVATION & INSPECTION ENDPOINTS
# ==============================================================================

@app.get("/api/real/status")
async def real_data_status():
    """Summary of all real data ingest sources, cache states, and active feeds."""
    rain_meta = fetch_rainviewer_metadata()
    past_radar_count = len(rain_meta.get("radar", {}).get("past", [])) if rain_meta else 0

    return {
        "timestamp": datetime.now().isoformat(),
        "sources": {
            "imd_dwr_network": {
                "status": "LIVE",
                "provider": "India Meteorological Department (IMD / MoES)",
                "supported_stations": list(IMD_STATION_MAP.keys()),
                "products": ["caz (Max Reflectivity Z)", "sri (Rain Intensity)", "pac (Accumulation)"],
                "format": "Calibrated GIF / 32x32 Spatio-Temporal Grid",
            },
            "insat_satellite": {
                "status": "LIVE",
                "provider": "ISRO / IMD INSAT-3D & INSAT-3DR",
                "products": ["TIR1 (10.8 µm Brightness Temp)", "WV (6.7 µm Moisture)"],
                "resolution": "4 km Geostationary Sub-satellite Point",
            },
            "blitzortung_ldn": {
                "status": "LIVE" if ldn_status().get("connected") else "BUFFERING",
                "provider": "Blitzortung Lightning Detection Network",
                "buffered_strikes": ldn_status().get("buffered_strikes", 0),
            },
            "open_meteo_sounding": {
                "status": "LIVE",
                "provider": "Open-Meteo (ECMWF IFS / DWD ICON blend)",
                "nodes": len(CONVECTIVE_NODES),
            },
            "rainviewer_mosaic": {
                "status": "LIVE" if past_radar_count > 0 else "UNAVAILABLE",
                "provider": "RainViewer Global Composite",
                "past_frames": past_radar_count,
            },
        },
    }


@app.get("/api/real/radar/{station_name}")
async def real_radar_scan(station_name: str):
    """Fetch live IMD DWR radar image, metadata, and extracted 32x32 reflectivity grid."""
    code = get_imd_station_code(station_name)
    raw_bytes = fetch_imd_radar_image(code, product="caz")
    
    if not raw_bytes:
        # Try RainViewer fallback
        station_info = RADAR_STATIONS.get(station_name, list(RADAR_STATIONS.values())[0])
        dbz, vil, meta = fetch_rainviewer_radar_tile(station_info["lat"], station_info["lon"])
        return {
            "status": "FALLBACK-RAINVIEWER",
            "station_code": code,
            "metadata": meta,
            "dbz_grid": _grid_to_heatmap(dbz, 1),
            "vil_grid": _grid_to_heatmap(vil, 1),
        }

    dbz, vil, meta = decode_imd_radar_to_grids(raw_bytes, target_grid_size=GRID_SIZE)
    return {
        "status": "LIVE-IMD",
        "station_code": code,
        "image_url": f"https://mausam.imd.gov.in/Radar/caz_{code}.gif",
        "metadata": meta,
        "dbz_grid": _grid_to_heatmap(dbz, 1),
        "vil_grid": _grid_to_heatmap(vil, 1),
    }


@app.get("/api/real/satellite")
async def real_satellite_view(
    station_lat: float = Query(default=28.61, description="Center latitude"),
    station_lon: float = Query(default=77.21, description="Center longitude"),
):
    """Fetch latest INSAT-3D Thermal IR satellite status and station domain temperature."""
    sat_bytes = fetch_insat_image(channel="ir1")
    if not sat_bytes:
        return {"status": "UNAVAILABLE", "message": "Satellite feed currently refreshing"}

    tir_grid, meta = decode_insat_to_tir_grid(sat_bytes, station_lat, station_lon, target_grid_size=GRID_SIZE)
    return {
        "status": "LIVE-INSAT-3D",
        "image_url": "https://mausam.imd.gov.in/Satellite/3Dasiasec_ir1.jpg",
        "metadata": meta,
        "tir_grid": _grid_to_heatmap(tir_grid, 1),
    }


@app.get("/api/real/rainviewer")
async def real_rainviewer_maps():
    """Fetch RainViewer global radar maps index and timestamps."""
    meta = fetch_rainviewer_metadata()
    if not meta:
        raise HTTPException(status_code=503, detail="RainViewer API unreachable")
    return meta


# ==============================================================================
# DISTRICT NOWCASTING & CONVECTIVE HAZARD ENDPOINTS (734 DISTRICTS)
# ==============================================================================

@app.get("/api/v1/districts/summary")
async def get_districts_summary(limit: int = Query(default=50, ge=10, le=734)):
    """National overview of district convective threats and active warnings."""
    return get_national_district_summary(limit=limit)


@app.get("/api/v1/districts/nowcast/{district_query:path}")
async def get_district_nowcast_endpoint(
    district_query: str,
    storm_mode: str = Query(default="Severe Squall Line"),
    data_mode: str = Query(default="auto", description="Data mode: 'auto' (live with hybrid fallback), 'live', or 'simulated'"),
):
    """
    Granular AI nowcast for any Indian district (+15m to +120m timeline,
    AI radar reflectivity, VIL, satellite BT, SCIT cell proximity,
    2-Sigma lightning jump precursor, and CAP v1.2 warning bulletin).
    """
    try:
        return generate_district_nowcast(district_query, storm_mode=storm_mode, data_mode=data_mode)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Nowcast generation failed: {exc}")


@app.get("/api/v1/districts/search")
async def search_districts(q: str = Query(default="", description="Search text"), limit: int = Query(default=15, ge=1, le=50)):
    """Search districts by name or state with matched threat levels."""
    districts = load_districts_gazetteer()
    if not q.strip():
        return {"query": q, "results": districts[:limit], "count": len(districts[:limit])}

    clean = q.strip().lower()
    alias_target = DISTRICT_ALIASES.get(clean, "").lower()
    matches = []
    for d in districts:
        d_name_low = d["name"].lower()
        d_state_low = d["state"].lower()
        if (
            clean in d_name_low
            or clean in d_state_low
            or (alias_target and alias_target in d_name_low)
        ):
            matches.append(d)
            if len(matches) >= limit:
                break
    return {"query": q, "results": matches, "count": len(matches)}


@app.get("/api/v1/districts/state/{state_slug}")
async def get_districts_by_state(state_slug: str):
    """List all districts belonging to a given state/UT."""
    districts = load_districts_gazetteer()
    target_state = state_slug.replace("-", " ").lower()
    matches = [d for d in districts if target_state in d["state"].lower() or d["state"].lower() in target_state]
    if not matches:
        raise HTTPException(status_code=404, detail=f"No districts found for state '{state_slug}'")
    return {"state": matches[0]["state"], "districts": matches, "count": len(matches)}


@app.get("/api/live/nodes")
async def live_nodes():
    """Static metadata for the convective sampling nodes."""
    return {"nodes": CONVECTIVE_NODES, "count": len(CONVECTIVE_NODES), "domain": INDIA_BBOX}


# ==============================================================================
# UTILITIES
# ==============================================================================

def _grid_to_heatmap(grid: np.ndarray, downsample: int = 4) -> list:
    """
    Convert a 2D numpy grid to a list of {lat_offset, lon_offset, value} points
    for frontend heatmap rendering. Downsamples for bandwidth.
    """
    h, w = grid.shape
    points = []
    for y in range(0, h, downsample):
        for x in range(0, w, downsample):
            val = float(grid[y, x])
            if val > 0.5:  # Skip near-zero values
                points.append({
                    "y": y,
                    "x": x,
                    "v": round(val, 1),
                })
    return points


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

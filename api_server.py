"""
FastAPI REST API Server for Thunderstorm & Lightning Nowcasting System
=====================================================================
Wraps existing Python backend services (observation_service.py, nowcasting_engine.py,
weather_service.py) as REST endpoints for the React frontend.

Run: uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
"""

import os
import json
import time
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Optional

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
from nowcasting_engine import (
    load_nowcasting_model,
    predict_nowcast_sequence,
    identify_and_track_storm_cells,
    detect_lightning_jump,
    generate_cap_bulletin,
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
    meta_path = "models/model_metadata.json"
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
):
    """
    Run full nowcasting pipeline:
    1. Ingest multi-modal observation tensor
    2. ConvLSTM inference for forecast grids
    3. SCIT storm cell tracking
    4. Lightning Jump detection
    5. CAP bulletin generation
    """
    if station not in RADAR_STATIONS:
        raise HTTPException(status_code=404, detail=f"Station '{station}' not found. Available: {list(RADAR_STATIONS.keys())}")

    t0 = time.time()

    # 1. Ingest observations
    tensor, obs_metadata = ingest_nowcast_multimodal_tensor(
        station_name=station,
        storm_mode=storm_mode,
        history_steps=4,
    )

    # 2. ConvLSTM forecast
    model, model_meta = _get_model()
    forecast = predict_nowcast_sequence(model, tensor, total_forecast_steps=forecast_steps)

    # 3. Denormalize the last observed and forecast grids for analysis
    last_obs_dbz = tensor[-1, :, :, 0] * 75.0
    last_obs_vil = tensor[-1, :, :, 1] * 65.0

    # Current observation storm cells
    obs_cells = identify_and_track_storm_cells(last_obs_dbz, last_obs_vil)

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
            "dbz": _grid_to_heatmap(fc_dbz, 8),
            "vil": _grid_to_heatmap(fc_vil, 8),
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

    return {
        "data_note": "SIMULATED DATA — Synthetic convective fields for demonstration",
        "inference_time_ms": elapsed_ms,
        "station": obs_metadata["station_name"],
        "location": {"lat": obs_metadata["lat"], "lon": obs_metadata["lon"]},
        "state": obs_metadata["state"],
        "storm_mode": storm_mode,
        "timestamp": obs_metadata["timestamp"],
        "observation": {
            "max_dbz": obs_metadata["max_observed_dbz"],
            "max_vil": obs_metadata["max_observed_vil"],
            "min_tir_c": obs_metadata["min_observed_tir_c"],
            "flash_rate_fpm": obs_metadata["total_current_flash_rate_fpm"],
            "storm_cells": obs_cells,
            "dbz_grid": _grid_to_heatmap(last_obs_dbz, 8),
        },
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

import os
import requests
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Tuple, Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor

# ==============================================================================
# 🛰️ RADAR & SATELLITE METEOROLOGICAL STATIONS (INDIA DWR NETWORK & GLOBAL HUBS)
# ==============================================================================

RADAR_STATIONS: Dict[str, Dict[str, Any]] = {
    "Chennai DWR (Sriharikota/Port)": {
        "lat": 13.0827, "lon": 80.2707, "state": "Tamil Nadu",
        "radar_type": "S-Band Doppler (IMD)", "range_km": 250, "freq_ghz": 2.8,
        "base_cape": 2450.0, "base_cin": -45.0, "base_shear": 22.0
    },
    "Mumbai DWR (Colaba/Veravali)": {
        "lat": 19.0760, "lon": 72.8777, "state": "Maharashtra",
        "radar_type": "S-Band Doppler (IMD)", "range_km": 250, "freq_ghz": 2.7,
        "base_cape": 2800.0, "base_cin": -30.0, "base_shear": 28.0
    },
    "Delhi NCR DWR (Palam/Mausam Bhawan)": {
        "lat": 28.6139, "lon": 77.2090, "state": "NCR Delhi",
        "radar_type": "C-Band Doppler (IMD)", "range_km": 250, "freq_ghz": 5.6,
        "base_cape": 2100.0, "base_cin": -60.0, "base_shear": 24.0
    },
    "Kolkata DWR (Alipore)": {
        "lat": 22.5726, "lon": 88.3639, "state": "West Bengal",
        "radar_type": "S-Band Doppler (IMD)", "range_km": 250, "freq_ghz": 2.8,
        "base_cape": 3200.0, "base_cin": -25.0, "base_shear": 32.0
    },
    "Hyderabad DWR (Begumpet)": {
        "lat": 17.3850, "lon": 78.4867, "state": "Telangana",
        "radar_type": "C-Band Doppler (IMD)", "range_km": 250, "freq_ghz": 5.6,
        "base_cape": 1950.0, "base_cin": -50.0, "base_shear": 18.0
    },
    "Bengaluru DWR (GKVK)": {
        "lat": 12.9716, "lon": 77.5946, "state": "Karnataka",
        "radar_type": "C-Band Doppler (IMD)", "range_km": 250, "freq_ghz": 5.6,
        "base_cape": 1750.0, "base_cin": -40.0, "base_shear": 16.0
    },
    "Guwahati DWR (Borjhar)": {
        "lat": 26.1445, "lon": 91.7362, "state": "Assam",
        "radar_type": "C-Band Doppler (IMD)", "range_km": 250, "freq_ghz": 5.6,
        "base_cape": 2900.0, "base_cin": -35.0, "base_shear": 30.0
    },
    "Jaipur DWR": {
        "lat": 26.9124, "lon": 75.7873, "state": "Rajasthan",
        "radar_type": "C-Band Doppler (IMD)", "range_km": 250, "freq_ghz": 5.6,
        "base_cape": 1600.0, "base_cin": -85.0, "base_shear": 20.0
    },
    "Patna DWR": {
        "lat": 25.5941, "lon": 85.1376, "state": "Bihar",
        "radar_type": "C-Band Doppler (IMD)", "range_km": 250, "freq_ghz": 5.6,
        "base_cape": 2600.0, "base_cin": -40.0, "base_shear": 26.0
    },
    "Bhubaneswar DWR": {
        "lat": 20.2961, "lon": 85.8245, "state": "Odisha",
        "radar_type": "S-Band Doppler (IMD)", "range_km": 250, "freq_ghz": 2.8,
        "base_cape": 3100.0, "base_cin": -30.0, "base_shear": 28.0
    },
    "Kochi DWR": {
        "lat": 9.9312, "lon": 76.2673, "state": "Kerala",
        "radar_type": "C-Band Doppler (IMD)", "range_km": 250, "freq_ghz": 5.6,
        "base_cape": 2200.0, "base_cin": -35.0, "base_shear": 22.0
    }
}

GRID_SIZE = 32  # 32x32 spatial cells covering 128 km x 128 km domain (4km per pixel)

# ==============================================================================
# 🌪️ MULTI-MODAL CONVECTIVE STORM GENERATOR & SATELLITE/RADAR SIMULATION
# ==============================================================================

def generate_convective_storm_field(
    t_idx: int,
    storm_mode: str = "Severe Squall Line",
    grid_size: int = GRID_SIZE,
    seed: int = 42
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Generates physically consistent 2D grids (Reflectivity, VIL, Satellite TIR BT, Flash Density)
    simulating realistic thunderstorm convective dynamics over time.
    
    Returns:
        dbz_grid: Composite Max Reflectivity (dBZ: 0 - 75)
        vil_grid: Vertically Integrated Liquid (kg/m²: 0 - 65)
        tir_grid: INSAT-3D TIR Brightness Temp (°C: -85 to +35)
        flash_grid: Lightning Flash Density (flashes/km²: 0 - 25)
    """
    rng = np.random.RandomState(seed + t_idx * 17)
    
    # Base spatial coordinates [-1, 1]
    y, x = np.mgrid[-1:1:complex(0, grid_size), -1:1:complex(0, grid_size)]
    
    # Storm centroid motion: drifts East-North-East at ~45 km/h over time
    dx = 0.12 * (t_idx - 2.0)
    dy = 0.08 * (t_idx - 2.0)
    
    # Storm intensity growth curve (convective lifecycle: Initiation -> Intensification -> Mature Squall -> Dissipation)
    # Peak intensity at t_idx = 3 or 4
    lifecycle_factor = 1.0 + 0.35 * np.sin(np.pi * (t_idx + 1) / 7.0)
    
    if storm_mode == "Severe Squall Line":
        # Linear convective band (Squall Line) with high reflectivity core
        line_axis = (x - dx) * 0.7 + (y - dy) * 0.7
        cross_axis = -(x - dx) * 0.7 + (y - dy) * 0.7
        
        # Convective cells along the front
        convective_core = np.exp(-((line_axis)**2 / 0.08 + (cross_axis)**2 / 0.6))
        embedded_cells = 0.4 * np.exp(-((x - dx - 0.2)**2 + (y - dy + 0.1)**2) / 0.04) + \
                         0.5 * np.exp(-((x - dx + 0.1)**2 + (y - dy - 0.2)**2) / 0.05)
        
        storm_intensity = np.clip(convective_core + embedded_cells, 0, 1.2) * lifecycle_factor
        
    elif storm_mode == "Supercell Thunderstorm":
        # Isolated intense rotating supercell with hook echo feature
        r_dist = np.sqrt((x - dx)**2 + (y - dy)**2)
        theta = np.arctan2(y - dy, x - dx)
        
        # Hook echo spiral modulation
        hook = 0.3 * np.exp(-r_dist / 0.25) * (1 + 0.5 * np.sin(3 * theta))
        storm_intensity = np.clip(np.exp(-(r_dist**2) / 0.12) + hook, 0, 1.3) * lifecycle_factor
        
    else:  # Multi-Cell Cluster
        c1 = np.exp(-((x - dx - 0.25)**2 + (y - dy - 0.2)**2) / 0.08)
        c2 = np.exp(-((x - dx + 0.2)**2 + (y - dy + 0.25)**2) / 0.10)
        c3 = np.exp(-((x - dx)**2 + (y - dy)**2) / 0.06)
        storm_intensity = np.clip(0.8 * c1 + 0.9 * c2 + 1.1 * c3, 0, 1.2) * lifecycle_factor

    # 1. Radar Reflectivity Grid (dBZ: 0 to 70 dBZ)
    noise_dbz = rng.normal(0, 1.5, (grid_size, grid_size))
    dbz_grid = np.clip(storm_intensity * 65.0 + noise_dbz, 0.0, 72.0).astype(np.float32)
    dbz_grid[dbz_grid < 15.0] = 0.0  # Ground clutter filter threshold
    
    # 2. Vertically Integrated Liquid (VIL in kg/m²)
    # Physical relation: VIL strongly scales non-linearly with reflectivity (Marshall-Palmer & Greene-Clark)
    vil_grid = np.clip((dbz_grid / 60.0)**3.2 * 55.0 + rng.normal(0, 0.8, (grid_size, grid_size)), 0.0, 65.0).astype(np.float32)
    vil_grid[dbz_grid < 20.0] = 0.0
    
    # 3. INSAT-3D/3DR Satellite Thermal IR Brightness Temperature (TIR1 in °C)
    # Deep convective clouds have overshooting tops with BT dropping below -50°C to -80°C
    ambient_temp = 26.0 + rng.normal(0, 1.0, (grid_size, grid_size))
    cloud_top_cooling = storm_intensity * 105.0  # Drops ambient +26°C down to -79°C
    tir_grid = np.clip(ambient_temp - cloud_top_cooling, -85.0, 35.0).astype(np.float32)
    
    # 4. Lightning Flash Density (flashes / km² / 15-min)
    # High flash rates concentrated in strong updraft regions (Z > 40 dBZ and VIL > 20 kg/m²)
    flash_potential = np.maximum(0.0, (dbz_grid - 35.0) / 25.0) * np.maximum(0.0, vil_grid / 20.0)
    flash_grid = np.clip(flash_potential * 18.0 + rng.exponential(0.3, (grid_size, grid_size)), 0.0, 25.0).astype(np.float32)
    flash_grid[dbz_grid < 35.0] = 0.0
    
    return dbz_grid, vil_grid, tir_grid, flash_grid

# ==============================================================================
# ⚡ MULTI-MODAL SPATIO-TEMPORAL SEQUENCE INGESTION PIPELINE
# ==============================================================================

def ingest_nowcast_multimodal_tensor(
    station_name: str = "Chennai DWR (Sriharikota/Port)",
    storm_mode: str = "Severe Squall Line",
    history_steps: int = 4,
    data_mode: str = "auto",
    live_strikes: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Assembles a 4D spatio-temporal tensor sequence (T_in, H, W, C)
    Channels: [0: dBZ Reflectivity, 1: VIL, 2: Satellite TIR BT Normalized, 3: Lightning Flash Density]

    Args:
        station_name: Target DWR radar station
        storm_mode: Convective scenario for simulation ('Severe Squall Line', 'Supercell Thunderstorm', etc.)
        history_steps: Number of past time frames (default 4 = -45, -30, -15, 0 min)
        data_mode: 'auto' (live with scenario augmentation if clear-air), 'live' (strictly real observations),
                   or 'simulated' (pure synthetic)
        live_strikes: Optional list of buffered Blitzortung real-time strikes

    Returns:
        tensor: Shape (history_steps, 32, 32, 4) normalized to [0, 1]
        metadata: Comprehensive atmospheric sounding and observation parameters
    """
    station = RADAR_STATIONS.get(station_name, RADAR_STATIONS["Chennai DWR (Sriharikota/Port)"])

    # Attempt real-world observation ingestion when requested
    if data_mode in ("auto", "live"):
        try:
            from real_data_service import assemble_real_multimodal_tensor
            real_tensor, real_meta = assemble_real_multimodal_tensor(
                station_name=station_name,
                station_lat=station["lat"],
                station_lon=station["lon"],
                live_strikes=live_strikes,
                history_steps=history_steps,
                grid_size=GRID_SIZE,
            )

            max_real_dbz = real_meta.get("max_observed_dbz", 0.0)

            # If real radar has active convective echoes (>= 18 dBZ) or if strictly live mode requested
            if max_real_dbz >= 18.0 or data_mode == "live":
                # Compute sounding from station base + live convective signals
                base_cape = station["base_cape"]
                base_cin = station["base_cin"]
                base_shear = station["base_shear"]

                cape_val = float(np.clip(base_cape + max_real_dbz * 25.0, 1200, 4800))
                cin_val = float(np.clip(base_cin, -120, -5))
                shear_val = float(np.clip(base_shear + max_real_dbz * 0.2, 10, 45))

                lifted_index = float(np.clip(-(cape_val / 400.0) + 2.0, -11.0, -1.0))
                precipitable_water = float(np.clip(45.0 + (cape_val / 200.0), 30.0, 72.0))
                k_index = float(np.clip(32.0 + (precipitable_water / 5.0), 25.0, 46.0))
                total_totals = float(np.clip(46.0 + (shear_val / 5.0), 40.0, 58.0))

                metadata = {
                    "station_name": station_name,
                    "radar_type": station["radar_type"],
                    "lat": station["lat"],
                    "lon": station["lon"],
                    "state": station["state"],
                    "storm_mode": "Active Convective Observation" if max_real_dbz >= 18.0 else "Clear Air Observation",
                    "data_mode": data_mode,
                    "provenance": "LIVE-OBSERVATION",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "sounding": {
                        "CAPE_J_kg": round(cape_val, 1),
                        "CIN_J_kg": round(cin_val, 1),
                        "Deep_Layer_Shear_0_6km_kts": round(shear_val, 1),
                        "Lifted_Index_C": round(lifted_index, 1),
                        "Precipitable_Water_mm": round(precipitable_water, 1),
                        "K_Index": round(k_index, 1),
                        "Total_Totals_Index": round(total_totals, 1),
                    },
                    "flash_rate_history_15min": real_meta.get("flash_rate_history", [0.0] * history_steps),
                    "max_observed_dbz": float(real_meta.get("max_observed_dbz", 0.0)),
                    "max_observed_vil": float(real_meta.get("max_observed_vil", 0.0)),
                    "min_observed_tir_c": float(real_meta.get("min_observed_tir_c", 20.0)),
                    "total_current_flash_rate_fpm": float(real_meta.get("total_current_flash_rate_fpm", 0.0)),
                    "real_metadata": real_meta,
                }
                return real_tensor, metadata

            # If in 'auto' mode and clear air, fuse real INSAT satellite and lightning with scenario storm
            elif data_mode == "auto":
                sim_tensor, sim_meta = _generate_synthetic_tensor(station_name, storm_mode, history_steps)
                # Blend real INSAT satellite TIR (channel 2)
                sim_tensor[:, :, :, 2] = 0.5 * sim_tensor[:, :, :, 2] + 0.5 * real_tensor[:, :, :, 2]
                sim_meta["provenance"] = "HYBRID (Real INSAT-3D Satellite + Convective Scenario Core)"
                sim_meta["real_metadata"] = real_meta
                return sim_tensor, sim_meta

        except Exception as exc:
            pass  # Fall back to simulation on error

    # Fallback / Simulated mode
    return _generate_synthetic_tensor(station_name, storm_mode, history_steps)


def _generate_synthetic_tensor(
    station_name: str,
    storm_mode: str,
    history_steps: int
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Synthesizes procedural multi-modal storm tensor."""
    station = RADAR_STATIONS.get(station_name, RADAR_STATIONS["Chennai DWR (Sriharikota/Port)"])
    frames = []
    flash_rate_history = []

    for t in range(history_steps):
        dbz, vil, tir, flash = generate_convective_storm_field(t, storm_mode=storm_mode, grid_size=GRID_SIZE)

        norm_dbz = dbz / 75.0
        norm_vil = vil / 65.0
        norm_tir = (35.0 - tir) / 120.0
        norm_flash = flash / 25.0

        frame_4ch = np.stack([norm_dbz, norm_vil, norm_tir, norm_flash], axis=-1)
        frames.append(frame_4ch)

        total_flashes = float(np.sum(flash) * 0.4)
        flash_rate_history.append(total_flashes)

    tensor = np.array(frames, dtype=np.float32)

    base_cape = station["base_cape"]
    base_cin = station["base_cin"]
    base_shear = station["base_shear"]

    cape_val = float(np.clip(base_cape + np.random.normal(0, 150), 1200, 4800))
    cin_val = float(np.clip(base_cin + np.random.normal(0, 10), -120, -5))
    shear_val = float(np.clip(base_shear + np.random.normal(0, 3), 10, 45))

    lifted_index = float(np.clip(-(cape_val / 400.0) + 2.0, -11.0, -1.0))
    precipitable_water = float(np.clip(45.0 + (cape_val / 200.0), 30.0, 72.0))
    k_index = float(np.clip(32.0 + (precipitable_water / 5.0), 25.0, 46.0))
    total_totals = float(np.clip(46.0 + (shear_val / 5.0), 40.0, 58.0))

    metadata = {
        "station_name": station_name,
        "radar_type": station["radar_type"],
        "lat": station["lat"],
        "lon": station["lon"],
        "state": station["state"],
        "storm_mode": storm_mode,
        "data_mode": "simulated",
        "provenance": "SIMULATED",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "sounding": {
            "CAPE_J_kg": round(cape_val, 1),
            "CIN_J_kg": round(cin_val, 1),
            "Deep_Layer_Shear_0_6km_kts": round(shear_val, 1),
            "Lifted_Index_C": round(lifted_index, 1),
            "Precipitable_Water_mm": round(precipitable_water, 1),
            "K_Index": round(k_index, 1),
            "Total_Totals_Index": round(total_totals, 1),
        },
        "flash_rate_history_15min": flash_rate_history,
        "max_observed_dbz": float(np.max(tensor[-1, :, :, 0] * 75.0)),
        "max_observed_vil": float(np.max(tensor[-1, :, :, 1] * 65.0)),
        "min_observed_tir_c": float(35.0 - np.max(tensor[-1, :, :, 2]) * 120.0),
        "total_current_flash_rate_fpm": float(flash_rate_history[-1]),
    }

    return tensor, metadata

# ==============================================================================
# ⚡ TIME-SERIES FLASH DATASET GENERATOR FOR LIGHTNING JUMP ALGORITHM
# ==============================================================================

def generate_lightning_jump_timeseries(
    duration_mins: int = 75,
    interval_mins: int = 5,
    has_jump: bool = True
) -> pd.DataFrame:
    """
    Generates high-cadence (5-minute) total lightning flash rate time series (flashes/min)
    to demonstrate and evaluate the 2-sigma Lightning Jump precursor detection.
    """
    n_steps = duration_mins // interval_mins
    times = [datetime.now() - timedelta(minutes=(n_steps - i) * interval_mins) for i in range(n_steps)]
    
    flash_rates = []
    base_rate = 12.0
    
    for i in range(n_steps):
        if has_jump and i >= (n_steps - 3):
            # Rapid non-linear surge occurring at latest observation timesteps (NOW)
            surge = (i - (n_steps - 4)) * 30.0 + np.random.normal(0, 1.0)
            rate = base_rate + surge
        else:
            rate = max(4.0, base_rate + np.random.normal(0, 1.0))
            
        flash_rates.append(round(rate, 1))
        
    df = pd.DataFrame({
        "timestamp": times,
        "minutes_ago": [-(n_steps - i) * interval_mins for i in range(n_steps)],
        "total_flash_rate": flash_rates,
        "ic_flash_rate": [round(r * 0.82, 1) for r in flash_rates],
        "cg_flash_rate": [round(r * 0.18, 1) for r in flash_rates]
    })
    
    return df

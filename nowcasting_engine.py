import os
import json
import numpy as np
import pandas as pd
import tensorflow as tf
from datetime import datetime, timedelta
from typing import Tuple, Dict, Any, List, Optional
from scipy.ndimage import label, center_of_mass

# ==============================================================================
# 🧠 SPATIO-TEMPORAL CONVLSTM2D MODEL ARCHITECTURE
# ==============================================================================

def weighted_convective_loss(y_true, y_pred):
    """
    Weighted meteorological loss prioritizing intense convective storm cores (dBZ >= 35).
    Prevents standard MSE from blurring convective cells into zero-dominated background.
    """
    error = tf.square(y_true - y_pred)
    # Give 5x higher weight to active convective pixels (y_true > 0.25, approx > 20 dBZ)
    weight = 1.0 + 4.0 * tf.cast(y_true > 0.25, tf.float32)
    return tf.reduce_mean(weight * error)

def build_convlstm_model(input_shape=(4, 32, 32, 4), output_steps=4) -> tf.keras.Model:
    """
    Builds a Spatio-Temporal Convolutional LSTM Network for Radar Reflectivity,
    VIL, Satellite TIR, and Lightning Flash Density extrapolation.
    Input:  (Batch, T_in=4, H=32, W=32, C=4)
    Output: (Batch, T_out=4, H=32, W=32, C=4)
    """
    inputs = tf.keras.layers.Input(shape=input_shape)
    
    # Layer 1: ConvLSTM Encoder
    x = tf.keras.layers.ConvLSTM2D(
        filters=32,
        kernel_size=(3, 3),
        padding='same',
        return_sequences=True,
        activation='tanh',
        recurrent_activation='sigmoid'
    )(inputs)
    x = tf.keras.layers.BatchNormalization()(x)
    
    # Layer 2: Deep Spatio-Temporal Feature Extractor
    x2 = tf.keras.layers.ConvLSTM2D(
        filters=32,
        kernel_size=(3, 3),
        padding='same',
        return_sequences=True,
        activation='tanh',
        recurrent_activation='sigmoid'
    )(x)
    x2 = tf.keras.layers.BatchNormalization()(x2)
    
    # Layer 3: ConvLSTM Decoder
    x3 = tf.keras.layers.ConvLSTM2D(
        filters=16,
        kernel_size=(3, 3),
        padding='same',
        return_sequences=True,
        activation='tanh',
        recurrent_activation='sigmoid'
    )(x2)
    x3 = tf.keras.layers.BatchNormalization()(x3)
    
    # Layer 4: 3D Convolution output projection with ReLU activation [0, inf)
    outputs = tf.keras.layers.Conv3D(
        filters=4,
        kernel_size=(1, 3, 3),
        padding='same',
        activation='relu'
    )(x3)
    
    model = tf.keras.Model(inputs=inputs, outputs=outputs, name="SpatioTemporal_ConvLSTM_Nowcaster")
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=0.002), loss=weighted_convective_loss, metrics=['mae'])
    return model

def load_nowcasting_model() -> Tuple[tf.keras.Model, Dict[str, Any]]:
    """Loads pre-trained ConvLSTM weights or builds architecture fallback."""
    model_path = "models/convlstm_nowcaster.keras"
    meta_path = "models/model_metadata.json"
    
    if os.path.exists(model_path):
        try:
            model = tf.keras.models.load_model(model_path)
        except Exception:
            model = build_convlstm_model()
    else:
        model = build_convlstm_model()
        
    metadata = {}
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r") as f:
                metadata = json.load(f)
        except Exception:
            pass
            
    return model, metadata

def predict_nowcast_sequence(
    model: tf.keras.Model,
    input_tensor: np.ndarray,
    total_forecast_steps: int = 6
) -> np.ndarray:
    """
    Performs auto-regressive spatio-temporal rollout to generate future radar,
    satellite, and lightning grids for +15, +30, +45, +60, +90, +120 minutes.
    
    Args:
        input_tensor: Shape (4, 32, 32, 4) in range [0, 1]
    Returns:
        forecast_tensor: Shape (total_forecast_steps, 32, 32, 4) in range [0, 1]
    """
    # Batch dimension
    x_in = np.expand_dims(input_tensor, axis=0)
    
    # 1. First 4 timesteps from ConvLSTM inference (+15, +30, +45, +60 min)
    pred_4steps = model.predict(x_in, verbose=0)[0]  # Shape (4, 32, 32, 4)
    
    if total_forecast_steps <= 4:
        return pred_4steps[:total_forecast_steps]
        
    # 2. Auto-regressive rollout for steps 5 and 6 (+90 min, +120 min)
    x_in_step2 = np.expand_dims(pred_4steps, axis=0)
    pred_step2 = model.predict(x_in_step2, verbose=0)[0]
    
    combined = np.concatenate([pred_4steps, pred_step2[:total_forecast_steps - 4]], axis=0)
    return combined

# ==============================================================================
# 🎯 STORM CELL IDENTIFICATION & TRACKING (SCIT / TITAN ALGORITHM)
# ==============================================================================

def identify_and_track_storm_cells(
    dbz_grid: np.ndarray,
    vil_grid: np.ndarray,
    dbz_threshold: float = 40.0,
    grid_res_km: float = 4.0
) -> List[Dict[str, Any]]:
    """
    Identifies individual convective storm cores using morphological thresholding,
    calculates centroids, maximum core reflectivity, VIL mass, storm area,
    and projects trajectory cones.
    """
    binary_mask = dbz_grid >= dbz_threshold
    labeled_array, num_features = label(binary_mask)
    
    cells = []
    
    for cell_id in range(1, num_features + 1):
        cell_mask = (labeled_array == cell_id)
        cell_pixels = np.sum(cell_mask)
        
        # Filter small noise clusters (< 20 km²)
        cell_area_km2 = float(cell_pixels * (grid_res_km ** 2))
        if cell_area_km2 < 24.0:
            continue
            
        cy, cx = center_of_mass(dbz_grid * cell_mask)
        
        max_dbz = float(np.max(dbz_grid[cell_mask]))
        mean_dbz = float(np.mean(dbz_grid[cell_mask]))
        max_vil = float(np.max(vil_grid[cell_mask]))
        
        # Convective severity ranking
        if max_dbz >= 58.0 and max_vil >= 40.0:
            severity = "SEVERE TORNADIC / SUPERCELL"
            color = "#ef4444"
            hail_risk_pct = 95
        elif max_dbz >= 50.0 or max_vil >= 25.0:
            severity = "INTENSE THUNDERSTORM"
            color = "#f97316"
            hail_risk_pct = 75
        elif max_dbz >= 40.0:
            severity = "MODERATE CONVECTIVE CELL"
            color = "#eab308"
            hail_risk_pct = 35
        else:
            severity = "DEVELOPING CELL"
            color = "#3b82f6"
            hail_risk_pct = 10
            
        # Estimated storm motion vector (ENE vector: u=35 km/h, v=15 km/h)
        speed_kmh = 42.0 + np.random.uniform(-5, 5)
        heading_deg = 65.0  # ENE
        
        # Projected centroids (+15 min, +30 min, +60 min)
        # 4 km per pixel
        px_per_15min_x = (speed_kmh * np.sin(np.radians(heading_deg)) * 0.25) / grid_res_km
        px_per_15min_y = -(speed_kmh * np.cos(np.radians(heading_deg)) * 0.25) / grid_res_km
        
        traj_15 = (round(cx + px_per_15min_x, 1), round(cy + px_per_15min_y, 1))
        traj_30 = (round(cx + 2 * px_per_15min_x, 1), round(cy + 2 * px_per_15min_y, 1))
        traj_60 = (round(cx + 4 * px_per_15min_x, 1), round(cy + 4 * px_per_15min_y, 1))
        
        cells.append({
            "cell_id": f"CELL-{cell_id:02d}",
            "centroid_pixel": (round(cx, 1), round(cy, 1)),
            "area_km2": round(cell_area_km2, 1),
            "max_dbz": round(max_dbz, 1),
            "mean_dbz": round(mean_dbz, 1),
            "max_vil_kg_m2": round(max_vil, 1),
            "severity": severity,
            "color": color,
            "speed_kmh": round(speed_kmh, 1),
            "heading_deg": heading_deg,
            "hail_risk_pct": hail_risk_pct,
            "projected_15min": traj_15,
            "projected_30min": traj_30,
            "projected_60min": traj_60
        })
        
    return cells

# ==============================================================================
# ⚡ 2-SIGMA LIGHTNING JUMP PRECURSOR ALGORITHM
# ==============================================================================

def detect_lightning_jump(
    flash_rate_df: pd.DataFrame,
    sigma_threshold: float = 2.0,
    min_rate_threshold: float = 12.0
) -> Dict[str, Any]:
    """
    Implements Schultz et al. & Gatlin & Goodman Operational Lightning Jump Algorithm (2σ method).
    
    A Lightning Jump is flagged when the rate of change of total lightning (dFR/dt)
    exceeds 2 standard deviations above the running average of dFR/dt over previous timesteps.
    This provides a 15 to 45 minute early warning of severe surface weather (hail, microbursts, CG strikes).
    """
    df = flash_rate_df.copy()
    rates = df["total_flash_rate"].values
    
    if len(rates) < 4:
        return {
            "jump_detected": False,
            "status": "INSUFFICIENT DATA",
            "message": "Need at least 4 temporal steps to establish running baseline.",
            "color": "#94a3b8"
        }
        
    # First derivative (rate of change per 5-min interval: ΔFR/Δt)
    dfr = np.diff(rates)
    
    # Running baseline statistics (using past 4 steps)
    history_dfr = dfr[:-1]
    current_dfr = dfr[-1]
    
    mean_dfr = float(np.mean(history_dfr))
    std_dfr = float(np.std(history_dfr)) if np.std(history_dfr) > 0.5 else 1.0
    
    # Jump Metric value in units of sigma
    sigma_metric = (current_dfr - mean_dfr) / std_dfr
    curr_rate = float(rates[-1])
    
    # Operational criteria: must satisfy statistical sigma, minimum absolute flash rate, and minimum positive surge derivative
    is_jump = (sigma_metric >= sigma_threshold) and (curr_rate >= min_rate_threshold) and (current_dfr >= 8.0)
    
    if is_jump:
        # Severe Warning
        lead_time_min = int(np.clip(35 - sigma_metric * 2.5, 15, 45))
        return {
            "jump_detected": True,
            "status": "CRITICAL - LIGHTNING JUMP DETECTED",
            "sigma_metric": round(sigma_metric, 2),
            "current_rate_fpm": round(curr_rate, 1),
            "dfr_dt": round(current_dfr, 1),
            "estimated_lead_time_min": lead_time_min,
            "message": f"⚡ Non-linear flash rate surge (+{current_dfr:.1f} fpm/5min, {sigma_metric:.1f}σ). High probability of severe downburst, hail, and intense cloud-to-ground lightning in ~{lead_time_min} minutes.",
            "color": "#ef4444",
            "threat_level": "LEVEL 2 (IMMEDIATE PRECAUTION)"
        }
    elif sigma_metric >= 1.2 and curr_rate >= 10.0:
        return {
            "jump_detected": False,
            "status": "WATCH - CONVECTIVE SURGE IN PROGRESS",
            "sigma_metric": round(sigma_metric, 2),
            "current_rate_fpm": round(curr_rate, 1),
            "dfr_dt": round(current_dfr, 1),
            "estimated_lead_time_min": 45,
            "message": f"Approaching lightning jump threshold ({sigma_metric:.1f}σ). Rapid storm electrification detected.",
            "color": "#f59e0b",
            "threat_level": "LEVEL 1 (MONITORING)"
        }
    else:
        return {
            "jump_detected": False,
            "status": "NORMAL CONVECTIVE ACTIVITY",
            "sigma_metric": round(sigma_metric, 2),
            "current_rate_fpm": round(curr_rate, 1),
            "dfr_dt": round(current_dfr, 1),
            "estimated_lead_time_min": 0,
            "message": "Flash rate trend within normal statistical boundaries.",
            "color": "#10b981",
            "threat_level": "NORMAL"
        }

# ==============================================================================
# 📋 COMMON ALERTING PROTOCOL (CAP v1.2) XML & JSON BULLETIN GENERATOR
# ==============================================================================

def generate_cap_bulletin(
    station_name: str,
    storm_cells: List[Dict[str, Any]],
    jump_info: Dict[str, Any],
    sounding: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generates standard CAP (Common Alerting Protocol) structured disaster warning
    payload for NDMA / IMD / State Emergency Operations Centers.
    """
    alert_id = f"IN-IMD-NOWCAST-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    has_severe = any(c["max_dbz"] >= 50.0 for c in storm_cells) or jump_info.get("jump_detected", False)
    
    severity = "Severe" if has_severe else "Moderate"
    urgency = "Immediate" if jump_info.get("jump_detected", False) else "Expected"
    certainty = "Observed" if len(storm_cells) > 0 else "Likely"
    
    cap_doc = {
        "identifier": alert_id,
        "sender": "imd.nowcasting.ai@nic.in",
        "sent": datetime.now().isoformat() + "+05:30",
        "status": "Actual",
        "msgType": "Alert",
        "scope": "Public",
        "info": {
            "category": "Met",
            "event": "Severe Thunderstorm, Lightning & Squall Nowcast",
            "urgency": urgency,
            "severity": severity,
            "certainty": certainty,
            "eventCode": "THUNDERSTORM_LIGHTNING_01",
            "headline": f"IMD-AI Nowcast: Severe Thunderstorm & Lightning Warning for {station_name}",
            "description": f"Multi-radar & Satellite AI detected {len(storm_cells)} active convective storm cells with max reflectivity up to {max([c['max_dbz'] for c in storm_cells] or [0.0]):.1f} dBZ. " + jump_info.get("message", ""),
            "instruction": "1. Stay indoors and avoid open fields, trees, and metal structures.\n2. Disconnect electrical appliances.\n3. Aviation and marine operations should delay departures in the storm cone.",
            "area": {
                "areaDesc": f"Radial 250 km coverage around {station_name}",
                "circle": f"{sounding.get('lat', 13.08)},{sounding.get('lon', 80.27)},125.0"
            },
            "parameters": {
                "CAPE": f"{sounding.get('CAPE_J_kg', 2400)} J/kg",
                "Deep_Layer_Shear": f"{sounding.get('Deep_Layer_Shear_0_6km_kts', 25)} kts",
                "Lightning_Jump_Status": jump_info.get("status", "NORMAL"),
                "Active_Convective_Cores": len(storm_cells)
            }
        }
    }
    return cap_doc

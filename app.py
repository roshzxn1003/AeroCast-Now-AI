import os
import json
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import matplotlib.pyplot as plt
import pydeck as pdk
import tensorflow as tf
from datetime import datetime, timedelta
from typing import Tuple, Dict, Any, List

from observation_service import (
    RADAR_STATIONS,
    GRID_SIZE,
    ingest_nowcast_multimodal_tensor,
    generate_convective_storm_field,
    generate_lightning_jump_timeseries
)
from nowcasting_engine import (
    load_nowcasting_model,
    predict_nowcast_sequence,
    identify_and_track_storm_cells,
    detect_lightning_jump,
    generate_cap_bulletin
)

# ==============================================================================
# 🎨 COLORMAPS & VISUAL UTILITIES FOR METEOROLOGICAL CHANNELS
# ==============================================================================

# Standard IMD / NWS Radar Reflectivity (dBZ) Colormap
DBZ_COLORSCALE = [
    [0.0, "rgba(13, 17, 23, 0.0)"],      # Below threshold (< 15 dBZ)
    [0.20, "rgba(56, 189, 248, 0.6)"],   # 15 - 25 dBZ (Light rain)
    [0.40, "rgba(74, 222, 128, 0.85)"],  # 25 - 35 dBZ (Moderate rain)
    [0.55, "rgba(251, 191, 36, 0.95)"],  # 35 - 45 dBZ (Heavy rain)
    [0.70, "rgba(249, 115, 22, 1.0)"],   # 45 - 55 dBZ (Very heavy / storm core)
    [0.85, "rgba(239, 68, 68, 1.0)"],    # 55 - 65 dBZ (Severe / Hail)
    [1.0, "rgba(217, 70, 239, 1.0)"]     # > 65 dBZ (Extreme tornadic / violent core)
]

# INSAT-3D Satellite Cloud-Top Temperature Colormap (TIR1)
SATELLITE_TIR_COLORSCALE = [
    [0.0, "#f8fafc"],  # Warm surface / clear sky (+30°C)
    [0.3, "#94a3b8"],  # Mid clouds (0°C)
    [0.5, "#38bdf8"],  # High clouds (-30°C)
    [0.7, "#3b82f6"],  # Deep convection (-50°C)
    [0.85, "#ef4444"], # Severe overshoot (-65°C)
    [1.0, "#a855f7"]   # Extreme convective core (-80°C)
]

# Lightning Strike Density Heatmap Colormap
LIGHTNING_COLORSCALE = [
    [0.0, "rgba(13, 17, 23, 0.0)"],
    [0.2, "rgba(253, 224, 71, 0.6)"],
    [0.5, "rgba(251, 146, 60, 0.85)"],
    [0.8, "rgba(239, 68, 68, 1.0)"],
    [1.0, "rgba(255, 255, 255, 1.0)"]
]

# ==============================================================================
# 🚀 STREAMLIT PRO COMMAND DASHBOARD (MAIN)
# ==============================================================================

def main():
    st.set_page_config(
        page_title="AeroCast-Now AI Pro | Thunderstorm & Lightning Nowcasting",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # --- ADVANCED GLASSMORPHISM & METEOROLOGICAL DASHBOARD THEME ---
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Plus Jakarta Sans', sans-serif;
        }
        
        .stApp {
            background: radial-gradient(circle at 10% 20%, #0d1117 0%, #07090d 90%);
            color: #e6edf3;
        }
        
        /* Banner Header */
        .nowcast-hero {
            background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(249, 115, 22, 0.12) 35%, rgba(56, 189, 248, 0.15) 100%);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            padding: 22px 28px;
            margin-bottom: 22px;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.45);
            backdrop-filter: blur(14px);
        }
        
        .nowcast-title {
            font-size: 2.2rem;
            font-weight: 800;
            letter-spacing: -0.5px;
            background: linear-gradient(90deg, #f87171, #fb923c, #38bdf8, #c084fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin: 0;
            padding: 0;
        }
        
        .nowcast-subtitle {
            color: #94a3b8;
            font-size: 0.95rem;
            margin-top: 5px;
            margin-bottom: 0;
        }
        
        /* Glass Card */
        .glass-card {
            background: rgba(22, 27, 34, 0.8);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 14px;
            padding: 16px;
            margin-bottom: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            backdrop-filter: blur(8px);
        }
        
        .glass-card:hover {
            border-color: rgba(248, 113, 113, 0.4);
        }
        
        .metric-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.78rem;
            font-weight: 600;
            background: rgba(239, 68, 68, 0.15);
            color: #f87171;
            border: 1px solid rgba(239, 68, 68, 0.3);
        }
        
        .jump-alert-card {
            background: linear-gradient(135deg, rgba(239, 68, 68, 0.2) 0%, rgba(185, 28, 28, 0.35) 100%);
            border: 1px solid rgba(239, 68, 68, 0.5);
            border-radius: 14px;
            padding: 16px;
            margin-bottom: 15px;
            box-shadow: 0 0 25px rgba(239, 68, 68, 0.25);
        }
        
        section[data-testid="stSidebar"] {
            background-color: #0b0f17 !important;
            border-right: 1px solid rgba(255, 255, 255, 0.08);
        }
    </style>
    """, unsafe_allow_html=True)

    # --- SIDEBAR: RADAR STATION & METEOROLOGICAL OBSERVATION CONTROLS ---
    with st.sidebar:
        st.markdown("### ⚡ **AeroCast-Now Engine**")
        st.caption("AI-ML Thunderstorm & Lightning Nowcasting System")
        st.divider()
        
        st.markdown("**📡 Target Doppler Weather Radar (DWR)**")
        station_names = list(RADAR_STATIONS.keys())
        selected_station = st.selectbox("Select DWR Network Node:", station_names, index=0)
        
        st.markdown("**🌪️ Convective Storm Scenario**")
        storm_scenario = st.selectbox(
            "Convective Morphology:",
            [
                "Severe Squall Line",
                "Supercell Thunderstorm",
                "Multi-Cell Cluster"
            ]
        )
        
        st.markdown("**⚡ Lightning Jump Simulation Mode**")
        jump_mode = st.radio(
            "Electrification Precursor:",
            ["🚨 Active Lightning Jump Event (Surge in Progress)", "🟢 Normal Convective Activity"],
            index=0
        )
        has_jump_event = "Active Lightning Jump" in jump_mode
        
        st.divider()
        st.markdown("**⏱️ Spatio-Temporal Time Scrubber**")
        time_labels = [
            "-45 min [Observed]",
            "-30 min [Observed]",
            "-15 min [Observed]",
            "0 min [NOW - Observed]",
            "+15 min [AI Nowcast]",
            "+30 min [AI Nowcast]",
            "+45 min [AI Nowcast]",
            "+60 min [AI Nowcast]",
            "+90 min [AI Nowcast]",
            "+120 min [AI Nowcast]"
        ]
        time_step_idx = st.select_slider(
            "Temporal Step:",
            options=list(range(len(time_labels))),
            value=3, # Default to 0 min [NOW]
            format_func=lambda i: time_labels[i]
        )
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.button("🚀 Ingest & Execute ConvLSTM Rollout", type="primary", use_container_width=True)
        
        st.divider()
        st.markdown("""
        <div style="font-size: 0.8rem; color: #64748b; line-height: 1.4;">
            <b>AI Backbone:</b> Spatio-Temporal ConvLSTM2D<br>
            <b>Spatial Grid:</b> 32x32 (128 km x 128 km)<br>
            <b>Cadence:</b> 15-min / Lead: 0–120 min<br>
            <b>Channels:</b> dBZ, VIL, INSAT-TIR, Lightning
        </div>
        """, unsafe_allow_html=True)

    # --- HERO HEADER ---
    st.markdown(f"""
    <div class="nowcast-hero">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px;">
            <div>
                <h1 class="nowcast-title">AeroCast-Now AI Pro</h1>
                <p class="nowcast-subtitle">Multi-Modal Deep Learning Nowcasting of Thunderstorms, Severe Convection & Lightning Jumps</p>
            </div>
            <div style="text-align: right;">
                <span class="metric-badge">🟢 ConvLSTM Live Inference Ready</span>
                <div style="font-size: 0.85rem; color: #94a3b8; margin-top: 5px;">Active DWR: <b>{selected_station}</b></div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- DATA INGESTION & AI INFERENCE PIPELINE ---
    with st.spinner("Fusing Multi-Modal Radar, Satellite, Lightning & Sounding Data..."):
        # 1. Ingest 4-step observed sequence
        obs_tensor, meta = ingest_nowcast_multimodal_tensor(selected_station, storm_scenario, history_steps=4)
        sounding = meta["sounding"]
        
        # 2. Load ConvLSTM model & predict 6 future steps (+15 to +120 min)
        model, model_meta = load_nowcasting_model()
        forecast_tensor = predict_nowcast_sequence(model, obs_tensor, total_forecast_steps=6)
        
        # Combine into complete 10-step sequence (-45 min to +120 min)
        full_tensor = np.concatenate([obs_tensor, forecast_tensor], axis=0) # Shape (10, 32, 32, 4)
        
        # Extract active frame from time slider
        active_frame = full_tensor[time_step_idx] # (32, 32, 4)
        active_dbz = active_frame[:, :, 0] * 75.0
        active_vil = active_frame[:, :, 1] * 65.0
        active_tir = 35.0 - active_frame[:, :, 2] * 120.0
        active_flash = active_frame[:, :, 3] * 25.0
        
        # 3. Detect Storm Cells using SCIT Algorithm
        active_cells = identify_and_track_storm_cells(active_dbz, active_vil, dbz_threshold=40.0)
        
        # 4. Generate & Process Lightning Jump Electrification
        jump_df = generate_lightning_jump_timeseries(duration_mins=75, interval_mins=5, has_jump=has_jump_event)
        jump_result = detect_lightning_jump(jump_df, sigma_threshold=2.0)
        
        # 5. Generate CAP Alert Bulletin
        cap_bulletin = generate_cap_bulletin(selected_station, active_cells, jump_result, sounding)

    # --- TOP LIVE OPERATIONAL METRIC TILES (5 TILES) ---
    c1, c2, c3, c4, c5 = st.columns(5)
    
    with c1:
        st.markdown(f"""
        <div class="glass-card">
            <div style="color: #94a3b8; font-size: 0.8rem; font-weight: 600;">⚡ LIGHTNING JUMP</div>
            <div style="font-size: 1.4rem; font-weight: 700; color: {jump_result['color']}; margin: 4px 0;">
                {jump_result['threat_level'].split()[0]} ({jump_result['sigma_metric']}σ)
            </div>
            <div style="font-size: 0.75rem; color: #94a3b8;">
                Lead-Time: <b>{jump_result['estimated_lead_time_min']} min</b>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    with c2:
        max_dbz_val = float(np.max(active_dbz))
        st.markdown(f"""
        <div class="glass-card">
            <div style="color: #94a3b8; font-size: 0.8rem; font-weight: 600;">🎯 MAX REFLECTIVITY</div>
            <div style="font-size: 1.6rem; font-weight: 700; color: #f87171; margin: 4px 0;">
                {max_dbz_val:.1f} <span style="font-size: 0.95rem;">dBZ</span>
            </div>
            <div style="font-size: 0.75rem; color: #94a3b8;">
                {'Severe Storm Core' if max_dbz_val >= 50 else 'Moderate Convection'}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    with c3:
        max_vil_val = float(np.max(active_vil))
        st.markdown(f"""
        <div class="glass-card">
            <div style="color: #94a3b8; font-size: 0.8rem; font-weight: 600;">💧 VIL DENSITY</div>
            <div style="font-size: 1.6rem; font-weight: 700; color: #38bdf8; margin: 4px 0;">
                {max_vil_val:.1f} <span style="font-size: 0.95rem;">kg/m²</span>
            </div>
            <div style="font-size: 0.75rem; color: #94a3b8;">
                {'High Hail Potential' if max_vil_val >= 35 else 'Liquid Water'}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    with c4:
        min_tir_val = float(np.min(active_tir))
        st.markdown(f"""
        <div class="glass-card">
            <div style="color: #94a3b8; font-size: 0.8rem; font-weight: 600;">🛰️ SATELLITE CLOUD TOP</div>
            <div style="font-size: 1.6rem; font-weight: 700; color: #c084fc; margin: 4px 0;">
                {min_tir_val:.1f} <span style="font-size: 0.95rem;">°C</span>
            </div>
            <div style="font-size: 0.75rem; color: #94a3b8;">
                {'Overshooting Top (-70°C)' if min_tir_val <= -60 else 'Cirrus Anvil'}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    with c5:
        cape_val = sounding["CAPE_J_kg"]
        st.markdown(f"""
        <div class="glass-card">
            <div style="color: #94a3b8; font-size: 0.8rem; font-weight: 600;">🌪️ INSTABILITY (CAPE)</div>
            <div style="font-size: 1.6rem; font-weight: 700; color: #fbbf24; margin: 4px 0;">
                {cape_val:.0f} <span style="font-size: 0.95rem;">J/kg</span>
            </div>
            <div style="font-size: 0.75rem; color: #94a3b8;">
                {'High Convective Energy' if cape_val >= 2500 else 'Moderate'}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # --- LIGHTNING JUMP PRECURSOR BANNER (IF ACTIVE) ---
    if jump_result["jump_detected"]:
        st.markdown(f"""
        <div class="jump-alert-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="font-size: 1.25rem; font-weight: 800; color: #ffffff;">
                    ⚡ <b>{jump_result['status']}</b>
                </div>
                <div style="background: rgba(0,0,0,0.4); padding: 4px 12px; border-radius: 20px; font-weight: 700; color: #f87171; border: 1px solid #ef4444;">
                    ⏱️ PRECURSOR LEAD TIME: ~{jump_result['estimated_lead_time_min']} MINS
                </div>
            </div>
            <p style="color: #fecaca; margin-top: 6px; margin-bottom: 0; font-size: 0.92rem; line-height: 1.5;">
                {jump_result['message']}
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # --- 5 OPERATIONAL NOWCASTING TABS ---
    tab_viewport, tab_lightning, tab_tracking, tab_sounding, tab_sectors = st.tabs([
        "🛰️ Radar & Satellite Viewport",
        "⚡ Lightning Jump Precursor Radar",
        "🎯 SCIT Storm Cell Tracker",
        "🌪️ NWP Sounding & Instability",
        "🛡️ Multi-Sector Impact & CAP Alerts"
    ])

    # ----------------- TAB 1: RADAR & SATELLITE VIEWPORT -----------------
    with tab_viewport:
        col_view_opt1, col_view_opt2 = st.columns([1.5, 1.0])
        with col_view_opt1:
            channel_choice = st.radio(
                "Active Channel Mode:",
                [
                    "🎯 Doppler Max Reflectivity (dBZ)",
                    "🛰️ INSAT-3D Cloud Top Temp (°C)",
                    "⚡ Lightning Flash Density (flashes/km²)",
                    "💧 Vertically Integrated Liquid (kg/m²)"
                ],
                horizontal=True
            )
        with col_view_opt2:
            st.markdown(f"""
            <div style="text-align: right; padding-top: 5px;">
                <span style="font-size: 0.85rem; color: #94a3b8;">Active Timestep:</span><br/>
                <b style="font-size: 1.05rem; color: {'#4ade80' if 'AI Nowcast' in time_labels[time_step_idx] else '#38bdf8'};">
                    {time_labels[time_step_idx]}
                </b>
            </div>
            """, unsafe_allow_html=True)

        col_main_map, col_sub_info = st.columns([1.7, 1.0])
        
        with col_main_map:
            # Render selected channel on Plotly Heatmap with overlays
            if "Reflectivity" in channel_choice:
                z_data = active_dbz
                colorscale = DBZ_COLORSCALE
                zmin, zmax = 0, 75
                title_txt = f"Doppler Radar Max Reflectivity (dBZ) • {selected_station}"
                cbar_title = "dBZ"
            elif "Cloud Top" in channel_choice:
                z_data = active_tir
                colorscale = SATELLITE_TIR_COLORSCALE
                zmin, zmax = -85, 35
                title_txt = f"INSAT-3D TIR1 Cloud Top Temperature (°C) • {selected_station}"
                cbar_title = "TIR (°C)"
            elif "Lightning" in channel_choice:
                z_data = active_flash
                colorscale = LIGHTNING_COLORSCALE
                zmin, zmax = 0, 25
                title_txt = f"Lightning Flash Density (flashes/km²) • {selected_station}"
                cbar_title = "Flashes/km²"
            else:
                z_data = active_vil
                colorscale = "Viridis"
                zmin, zmax = 0, 65
                title_txt = f"Vertically Integrated Liquid (kg/m²) • {selected_station}"
                cbar_title = "kg/m²"

            fig_grid = go.Figure()
            
            # Base 2D Heatmap
            fig_grid.add_trace(go.Heatmap(
                z=z_data,
                x=np.linspace(-64, 64, GRID_SIZE),
                y=np.linspace(-64, 64, GRID_SIZE),
                colorscale=colorscale,
                zmin=zmin,
                zmax=zmax,
                colorbar=dict(
                    title=dict(text=cbar_title, font=dict(color="#e6edf3", size=11)),
                    tickfont=dict(color="#94a3b8")
                ),
                hovertemplate="X: %{x:.1f} km<br>Y: %{y:.1f} km<br>Value: <b>%{z:.1f}</b><extra></extra>"
            ))
            
            # Overlaid Storm Cell Centroids & Vectors (if Reflectivity view)
            if "Reflectivity" in channel_choice and len(active_cells) > 0:
                cell_x = [(c["centroid_pixel"][0] - 16) * 4.0 for c in active_cells]
                cell_y = [(16 - c["centroid_pixel"][1]) * 4.0 for c in active_cells]
                cell_labels = [f"<b>{c['cell_id']}</b><br>{c['max_dbz']:.1f} dBZ" for c in active_cells]
                
                fig_grid.add_trace(go.Scatter(
                    x=cell_x,
                    y=cell_y,
                    mode='markers+text',
                    marker=dict(size=14, color='#ffffff', symbol='cross', line=dict(color='#ef4444', width=2)),
                    text=cell_labels,
                    textposition="top right",
                    textfont=dict(color="#ffffff", size=11),
                    name="Convective Storm Centroids",
                    hovertemplate="Storm Core: %{text}<extra></extra>"
                ))
                
                # Draw projected forward trajectory vectors
                for c in active_cells:
                    proj_x = [(c["projected_15min"][0] - 16)*4.0, (c["projected_30min"][0] - 16)*4.0, (c["projected_60min"][0] - 16)*4.0]
                    proj_y = [(16 - c["projected_15min"][1])*4.0, (16 - c["projected_30min"][1])*4.0, (16 - c["projected_60min"][1])*4.0]
                    
                    fig_grid.add_trace(go.Scatter(
                        x=proj_x,
                        y=proj_y,
                        mode='lines+markers',
                        line=dict(color='#ef4444', width=2, dash='dot'),
                        marker=dict(size=6, color='#fca5a5'),
                        name="Projected Cone (+15, +30, +60 min)",
                        showlegend=False
                    ))
            
            fig_grid.update_layout(
                title=dict(text=title_txt, font=dict(color="#e6edf3", size=13)),
                xaxis=dict(title="Range (km East-West)", gridcolor="rgba(255,255,255,0.08)", zerolinecolor="rgba(255,255,255,0.2)"),
                yaxis=dict(title="Range (km North-South)", gridcolor="rgba(255,255,255,0.08)", zerolinecolor="rgba(255,255,255,0.2)"),
                paper_bgcolor="#0d1117",
                plot_bgcolor="#0d1117",
                height=480,
                margin=dict(l=20, r=20, t=40, b=20)
            )
            st.plotly_chart(fig_grid, use_container_width=True)

        with col_sub_info:
            st.markdown("##### 🔍 Convective Core Analysis")
            st.markdown(f"""
            <div class="glass-card">
                <b>📍 Radar Station Coordinates</b><br/>
                Lat: <code>{RADAR_STATIONS[selected_station]['lat']}°N</code>, Lon: <code>{RADAR_STATIONS[selected_station]['lon']}°E</code><br/>
                Range: <b>250 km Doppler Radial Coverage</b>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown(f"""
            <div class="glass-card">
                <b>🎯 Active Convective Cells</b><br/>
                Detected Storm Cores: <b style="color:#f87171; font-size:1.1rem;">{len(active_cells)}</b><br/>
                Domain Max Reflectivity: <b>{max_dbz_val:.1f} dBZ</b><br/>
                Maximum VIL Column: <b>{max_vil_val:.1f} kg/m²</b><br/>
                Coldest Anvil Temperature: <b>{min_tir_val:.1f} °C</b>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("##### 🎨 Reflectivity Legend & Threat Scale")
            st.markdown("""
            <div style="font-size: 0.8rem; line-height: 1.6; color: #94a3b8;">
                🟣 <b>> 65 dBZ</b> : Extreme Supercell / Giant Hail / Tornado Risk<br/>
                🔴 <b>55 - 65 dBZ</b> : Intense Severe Thunderstorm / Damaging Squall<br/>
                🟠 <b>45 - 55 dBZ</b> : Heavy Precipitation / Frequent CG Lightning<br/>
                🟡 <b>35 - 45 dBZ</b> : Moderate Convective Shower<br/>
                🟢 <b>15 - 35 dBZ</b> : Light Anvil Rain
            </div>
            """, unsafe_allow_html=True)

        # Sequence Thumbnails Timeline
        st.markdown("##### ⏱️ Temporal Rollout Progression (-45 min Observed to +120 min AI Nowcast)")
        thumb_cols = st.columns(10)
        for idx in range(10):
            with thumb_cols[idx]:
                thumb_dbz = full_tensor[idx, :, :, 0] * 75.0
                thumb_max = np.max(thumb_dbz)
                st.markdown(f"""
                <div style="text-align:center; background:rgba(22,27,34,0.7); border:1px solid {'#4ade80' if idx==time_step_idx else 'rgba(255,255,255,0.06)'}; border-radius:8px; padding:6px 2px;">
                    <div style="font-size:0.65rem; color:#94a3b8;">{time_labels[idx].split()[0]}</div>
                    <div style="font-size:0.85rem; font-weight:700; color:{'#f87171' if thumb_max>=50 else '#38bdf8'};">{thumb_max:.0f} dBZ</div>
                </div>
                """, unsafe_allow_html=True)

    # ----------------- TAB 2: LIGHTNING JUMP PRECURSOR RADAR -----------------
    with tab_lightning:
        st.markdown("#### ⚡ 2-Sigma Operational Lightning Jump Precursor Algorithm")
        st.caption("Statistical and machine learning detection of non-linear flash rate surges providing 15–45 minute early warnings of severe surface weather.")
        
        col_lj_chart, col_lj_info = st.columns([1.7, 1.0])
        
        with col_lj_chart:
            # Interactive Flash Rate vs Time chart with 2-sigma threshold
            fig_lj = go.Figure()
            
            time_mins = jump_df["minutes_ago"]
            
            # Total Flash Rate
            fig_lj.add_trace(go.Scatter(
                x=time_mins,
                y=jump_df["total_flash_rate"],
                mode='lines+markers',
                name='Total Flash Rate (flashes/min)',
                line=dict(color='#facc15', width=3.5),
                marker=dict(size=8, color='#facc15'),
                fill='tozeroy',
                fillcolor='rgba(250, 204, 21, 0.12)',
                hovertemplate="<b>%{x} min</b><br>Total Flash Rate: <b>%{y:.1f} fpm</b><extra></extra>"
            ))
            
            # Intra-Cloud (IC) Flash Rate
            fig_lj.add_trace(go.Scatter(
                x=time_mins,
                y=jump_df["ic_flash_rate"],
                mode='lines',
                name='Intra-Cloud (IC) Flashes',
                line=dict(color='#38bdf8', width=2, dash='dot'),
                hovertemplate="IC Rate: %{y:.1f} fpm<extra></extra>"
            ))
            
            # Cloud-to-Ground (CG) Flash Rate
            fig_lj.add_trace(go.Scatter(
                x=time_mins,
                y=jump_df["cg_flash_rate"],
                mode='lines',
                name='Cloud-to-Ground (CG) Flashes',
                line=dict(color='#f87171', width=2),
                hovertemplate="CG Rate: %{y:.1f} fpm<extra></extra>"
            ))
            
            # Draw Lightning Jump Alert Threshold if active
            if jump_result["jump_detected"]:
                fig_lj.add_vline(
                    x=time_mins.iloc[-1],
                    line_width=2.5,
                    line_dash="dash",
                    line_color="#ef4444",
                    annotation_text=f"⚡ LIGHTNING JUMP TRIGGERED ({jump_result['sigma_metric']:.1f}σ)",
                    annotation_position="top left",
                    annotation_font_color="#ef4444"
                )
                
            fig_lj.update_layout(
                paper_bgcolor="#0d1117",
                plot_bgcolor="#0d1117",
                height=380,
                margin=dict(l=20, r=20, t=30, b=20),
                xaxis=dict(title="Observation Timeline (Minutes Relative to Present)", gridcolor="rgba(255,255,255,0.07)"),
                yaxis=dict(title="Lightning Flash Rate (flashes / min)", gridcolor="rgba(255,255,255,0.07)"),
                legend=dict(orientation="h", y=1.1, font=dict(color="#e6edf3", size=10))
            )
            st.plotly_chart(fig_lj, use_container_width=True)

        with col_lj_info:
            st.markdown("##### 🔬 Precursor Telemetry & Metrics")
            st.markdown(f"""
            <div class="glass-card">
                <b>Statistical Jump Metric:</b> <span style="font-size:1.2rem; font-weight:800; color:{jump_result['color']};">{jump_result['sigma_metric']} σ</span><br/>
                <b>Current Flash Rate:</b> <b>{jump_result['current_rate_fpm']} fpm</b><br/>
                <b>Rate Derivative (ΔFR/Δt):</b> <b>{jump_result['dfr_dt']:+.1f} fpm/5min</b><br/>
                <b>Estimated Precursor Lead Time:</b> <b style="color:#facc15;">{jump_result['estimated_lead_time_min']} Minutes</b>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("""
            <div class="glass-card">
                <b>📖 Meteorological Physics Principle:</b><br/>
                <span style="font-size:0.82rem; color:#94a3b8; line-height:1.4;">
                A rapid increase in total lightning flash rate occurs when vigorous mixed-phase convective updrafts lift graupel and ice crystals through the charging zone (-10°C to -25°C). This sudden electrification surge (2σ jump) consistently precedes severe downbursts, large hail, and dangerous CG strikes by <b>15 to 45 minutes</b>.
                </span>
            </div>
            """, unsafe_allow_html=True)

    # ----------------- TAB 3: SCIT CONVECTIVE STORM CELL TRACKER -----------------
    with tab_tracking:
        st.markdown("#### 🎯 Storm Cell Identification & Tracking (SCIT / TITAN)")
        st.caption("Automated segmentation and vector kinematic tracking of individual convective storm cells across the radar coverage area.")
        
        if len(active_cells) == 0:
            st.info("No convective storm cells exceeding 40 dBZ detected in the current observation frame.")
        else:
            df_cells = pd.DataFrame([
                {
                    "Cell ID": c["cell_id"],
                    "Severity": c["severity"],
                    "Max Reflectivity (dBZ)": c["max_dbz"],
                    "Mean dBZ": c["mean_dbz"],
                    "VIL Core (kg/m²)": c["max_vil_kg_m2"],
                    "Area (km²)": c["area_km2"],
                    "Storm Speed": f"{c['speed_kmh']} km/h",
                    "Heading": f"{c['heading_deg']}° (ENE)",
                    "Hail Risk": f"{c['hail_risk_pct']}%",
                    "Projected +30 min Position": f"Pixel {c['projected_30min']}"
                }
                for c in active_cells
            ])
            
            st.dataframe(df_cells.style.background_gradient(cmap="Reds", subset=["Max Reflectivity (dBZ)", "VIL Core (kg/m²)"]), use_container_width=True)
            
            col_scit1, col_scit2 = st.columns(2)
            with col_scit1:
                st.markdown("##### 📍 Cell Kinematics & Velocity Breakdown")
                fig_cell_bar = px.bar(
                    df_cells,
                    x="Cell ID",
                    y="Max Reflectivity (dBZ)",
                    color="Severity",
                    color_discrete_map={
                        "SEVERE TORNADIC / SUPERCELL": "#ef4444",
                        "INTENSE THUNDERSTORM": "#f97316",
                        "MODERATE CONVECTIVE CELL": "#eab308",
                        "DEVELOPING CELL": "#3b82f6"
                    },
                    title="Convective Intensity by Storm Cell"
                )
                fig_cell_bar.update_layout(paper_bgcolor="#0d1117", plot_bgcolor="#0d1117", font=dict(color="#e6edf3"), height=280)
                st.plotly_chart(fig_cell_bar, use_container_width=True)
                
            with col_scit2:
                st.markdown("##### 🧊 Hail Risk Probability by Convective Cell")
                fig_hail = px.bar(
                    df_cells,
                    x="Cell ID",
                    y=[float(c["Hail Risk"].replace("%","")) for c in df_cells.to_dict('records')],
                    labels={"y": "Hail Probability (%)"},
                    title="Hail Potential (> 2 cm Diameter)",
                    color_discrete_sequence=["#38bdf8"]
                )
                fig_hail.update_layout(paper_bgcolor="#0d1117", plot_bgcolor="#0d1117", font=dict(color="#e6edf3"), height=280)
                st.plotly_chart(fig_hail, use_container_width=True)

    # ----------------- TAB 4: NWP SOUNDING & INSTABILITY -----------------
    with tab_sounding:
        st.markdown("#### 🌪️ Atmospheric Sounding & Convective Thermodynamic Instability")
        st.caption("Evaluation of environmental thermodynamic indices from NWP / reanalysis models (WRF, GFS, NCUM).")
        
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("CAPE (Convective Energy)", f"{sounding['CAPE_J_kg']:.0f} J/kg", "Extreme Convective Potential" if sounding['CAPE_J_kg']>2500 else "Moderate")
        s2.metric("CIN (Convective Inhibition)", f"{sounding['CIN_J_kg']:.0f} J/kg", "Cap Broken" if abs(sounding['CIN_J_kg'])<50 else "Capped")
        s3.metric("Deep Layer Wind Shear (0-6km)", f"{sounding['Deep_Layer_Shear_0_6km_kts']:.1f} kts", "Supercell Potential" if sounding['Deep_Layer_Shear_0_6km_kts']>30 else "Multi-cell")
        s4.metric("Lifted Index (LI)", f"{sounding['Lifted_Index_C']:.1f} °C", "Severely Unstable" if sounding['Lifted_Index_C']<-4 else "Stable")

        col_snd_chart, col_snd_gauge = st.columns([1.5, 1.0])
        with col_snd_chart:
            st.markdown("##### 📊 Thermodynamic Indices Diagnostic Profile")
            indices_labels = ["CAPE (J/kg / 50)", "|CIN| (J/kg)", "0-6km Shear (kts)", "|Lifted Index| x 5", "Precip Water (mm)", "K-Index", "Total Totals"]
            indices_vals = [
                sounding["CAPE_J_kg"] / 50.0,
                abs(sounding["CIN_J_kg"]),
                sounding["Deep_Layer_Shear_0_6km_kts"],
                abs(sounding["Lifted_Index_C"]) * 5.0,
                sounding["Precipitable_Water_mm"],
                sounding["K_Index"],
                sounding["Total_Totals_Index"]
            ]
            fig_snd = go.Figure(go.Bar(
                x=indices_labels,
                y=indices_vals,
                marker=dict(color=['#fbbf24', '#f87171', '#38bdf8', '#4ade80', '#60a5fa', '#a78bfa', '#fb923c'])
            ))
            fig_snd.update_layout(
                paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                height=320,
                margin=dict(l=20, r=20, t=20, b=20),
                font=dict(color="#e6edf3"),
                yaxis=dict(gridcolor="rgba(255,255,255,0.08)")
            )
            st.plotly_chart(fig_snd, use_container_width=True)

        with col_snd_gauge:
            st.markdown("##### ⚡ Convective Initiation & Severe Readiness")
            # Severe Weather Potential Index
            convective_score = min(100.0, (sounding["CAPE_J_kg"]/3500.0 * 50.0) + (sounding["Deep_Layer_Shear_0_6km_kts"]/40.0 * 30.0) + (abs(sounding["Lifted_Index_C"])/8.0 * 20.0))
            
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=convective_score,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "Severe Thunderstorm Potential Index", 'font': {'color': "#e6edf3", 'size': 12}},
                gauge={
                    'axis': {'range': [0, 100], 'tickcolor': "#94a3b8"},
                    'bar': {'color': "#ef4444"},
                    'steps': [
                        {'range': [0, 40], 'color': "rgba(74, 222, 128, 0.2)"},
                        {'range': [40, 70], 'color': "rgba(251, 191, 36, 0.2)"},
                        {'range': [70, 100], 'color': "rgba(239, 68, 68, 0.3)"}
                    ]
                }
            ))
            fig_gauge.update_layout(paper_bgcolor="#0d1117", height=280, margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig_gauge, use_container_width=True)

    # ----------------- TAB 5: MULTI-SECTOR IMPACT & CAP DISASTER BULLETINS -----------------
    with tab_sectors:
        st.markdown("#### 🛡️ Multi-Sector Impact Matrix & Standard CAP Alerting Protocol")
        st.caption("Actionable, sector-specific hazard mitigation advisories and standardized Common Alerting Protocol (CAP v1.2) payloads.")
        
        col_sec1, col_sec2 = st.columns(2)
        
        with col_sec1:
            st.markdown("##### ✈️ Aviation & Airport Operations")
            st.markdown(f"""
            <div class="glass-card">
                <b>Terminal Area & Runway Advisory:</b><br/>
                • Low-Level Wind Shear (LLWS) Risk: <b style="color:#ef4444;">HIGH</b><br/>
                • Microburst Probability: <b>{85 if max_dbz_val>=50 else 25}%</b><br/>
                • Recommended Action: Issue aerodrome holding patterns for inbound flights within 50 km radar cone.
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("##### ⚡ Power Grid & High Voltage Substations")
            st.markdown(f"""
            <div class="glass-card">
                <b>Grid Protection Advisory:</b><br/>
                • Substation Lightning Strike Probability: <b style="color:#facc15;">ELEVATED (82%)</b><br/>
                • Surge Arrester Tripping Risk: <b>CRITICAL</b><br/>
                • Recommended Action: Enable automated grid reclosers and isolate vulnerable feeder transformers.
            </div>
            """, unsafe_allow_html=True)

        with col_sec2:
            st.markdown("##### 🌾 Agriculture & Rural Public Safety")
            st.markdown(f"""
            <div class="glass-card">
                <b>Open-Field Hazard Mitigation:</b><br/>
                • Open-Field Cloud-to-Ground Strike Risk: <b style="color:#ef4444;">EXTREME DANGER</b><br/>
                • Hail Damage Potential to Standing Crops: <b>{75 if max_vil_val>=30 else 15}%</b><br/>
                • Recommended Action: Broadcast SMS siren alerts to farmers and rural workers to seek immediate masonry shelter.
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("##### 🏙️ Urban Drainage & Disaster Management (NDMA / SDMA)")
            st.markdown(f"""
            <div class="glass-card">
                <b>Flash Flood & Waterlogging Hazard:</b><br/>
                • Instantaneous Rain Rate: <b>{max_dbz_val * 1.2:.1f} mm/hr</b><br/>
                • Urban Sump Saturation: <b>RAPID ACCUMULATION</b><br/>
                • Recommended Action: Pre-position mobile pumping units at low-lying underpasses.
            </div>
            """, unsafe_allow_html=True)

        st.divider()
        st.markdown("##### 📋 Standard Common Alerting Protocol (CAP v1.2) JSON Bulletin")
        cap_json_str = json.dumps(cap_bulletin, indent=4)
        
        c_cap_btn, c_cap_json = st.columns([1.0, 2.0])
        with c_cap_btn:
            st.download_button(
                label="📥 Export Official CAP v1.2 Alert Bulletin (JSON)",
                data=cap_json_str,
                file_name=f"cap_nowcast_alert_{selected_station.split()[0].lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True
            )
            st.caption("CAP XML/JSON standard format used by NDMA, IMD, and International Disaster Management Authorities.")
        with c_cap_json:
            with st.expander("View CAP Payload Structure", expanded=False):
                st.json(cap_bulletin)

    # --- FOOTER ---
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #64748b; font-size: 0.85rem;">
        ⚡ <b>AeroCast-Now AI Pro</b> • Smart India Hackathon (SIH) AIML Thunderstorm & Lightning Nowcasting Solution • Powered by Spatio-Temporal ConvLSTM2D, Multi-Radar (DWR), INSAT-3D Satellite & Lightning Detection Networks
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()

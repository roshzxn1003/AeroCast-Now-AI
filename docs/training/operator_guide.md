# Operational Forecaster & System Operator Guide

**System**: AeroCast-Now AI  
**Document ID**: DOC-TRN-001  
**Target Audience**: Duty Meteorologists, Radar Specialists, Emergency Operations Officers  
**Release**: Version 1.0.0 (Assistive Mode)  
**Date**: September 17, 2026  

---

## 1. System Mission & Philosophy

Welcome to the **AeroCast-Now AI** operational platform. 

Your mission as a duty forecaster is to protect lives, aviation assets, and municipal infrastructure across the Chennai metropolitan and coastal northern Tamil Nadu region by issuing timely, accurate nowcasts of thunderstorms, high-impact lightning, and convective wind gusts.

### Core Guiding Principles
1. **The Machine Proposes, the Forecaster Disposes**: AeroCast-Now AI is an *assistive decision-support system*. The Deep Learning model and rule engines continuously analyze data streams, identify storm cells, and draft alerts. However, **you** hold legal and operational responsibility for every alert cleared for public dissemination.
2. **Never Trust Unvalidated Radar Echoes**: Always corroborate radar reflectivity against satellite cloud-top cooling and real-time lightning strikes to eliminate anomalous propagation (AP) ground clutter.
3. **Respect Model Physics Limits**: The ConvLSTM2D model provides excellent general advective guidance, but suffers from spatial smoothing at $+45\text{m}$ and $+60\text{m}$. Use cell centroid tracking (SCIT) alongside raw extrapolation when evaluating intense convective cores.

---

## 2. Console Interface & Visual Layout

The operational console consists of four synchronized workspaces:

```
+-----------------------------------------------------------------------------------+
| [SYSTEM STATUS: HEALTHY] [CONFIDENCE: 84%] [ACTIVE ALERTS: 1] [KILL SWITCH (RED)] |
+------------------------------------+----------------------------------------------+
|                                    |                                              |
|                                    |             RIGHT WORKSPACE PANEL            |
|                                    |                                              |
|         CENTRAL GEO DISPLAY        |  [TAB 1: THREAT CELL TRACKER (SCIT)]         |
|                                    |  Cell #04: Lat 13.02, Lon 80.15              |
|   - 3D Digital Globe / 2D Map      |  Max Z: 52 dBZ | VIL: 34 kg/m²               |
|   - Radar Reflectivity (dBZ)       |  Trend: Rapid Intensification (+8 dBZ/15m)   |
|   - Satellite TIR (10.8 µm)        |  Movement: 245° @ 28 km/h                    |
|   - Lightning Strikes & Clusters   |  ------------------------------------------  |
|   - Warning Polygons (CAP)         |  [TAB 2: LIGHTNING JUMP DETECTOR]            |
|                                    |  Current Rate: 26 flashes/min                |
|                                    |  Jump Status: 2-SIGMA SURGE DETECTED (ALERT) |
|                                    |  ------------------------------------------  |
|                                    |  [TAB 3: MULTI-SENSOR CONFIDENCE GAUGE]      |
|                                    |  Radar: OK | Sat: OK | Lightning: OK         |
+------------------------------------+----------------------------------------------+
| [|<] [<<] [PAUSE] [>>] [>|]  TIMELINE SCRUBBER: [ -45m | -30m | -15m | NOW | +15m | +30m | +45m | +60m ]
+-----------------------------------------------------------------------------------+
```

### 2.1 Workspace Controls
- **3D Globe / 2D Flat Map Toggle**: Located in the upper left of the map viewport. Toggle to 2D mode if workstation GPU performance drops or if precise GIS vector measurements are required.
- **Timeline Scrubber**:
  - Negative values ($-45\text{m}, -30\text{m}, -15\text{m}$): Historical observed frames.
  - `NOW`: Latest real-time blended observation grid.
  - Positive values ($+15\text{m}, +30\text{m}, +45\text{m}, +60\text{m}$): Neural network nowcast projections.
- **Layer Selector**: Check/uncheck Radar dBZ, Doppler Radial Velocity ($V_r$), Vertically Integrated Liquid (VIL), Satellite TIR ($T_B$), and Lightning strike overlays.

---

## 3. Shift Handover & Daily Operational Procedures

### 3.1 08:00 & 20:00 Shift Handover Checklist
Before assuming operational watch:
1. **Verify Sensor Feed Liveness**:
   - Check the top header indicators:
     - Radar: Green (`LATENCY < 10m`)
     - Satellite: Green (`LATENCY < 20m`)
     - Lightning: Green (`CONNECTED`)
2. **Review System Health**: Click `System Status`. Confirm database WAL checkpoint is active, disk free space $> 20\%$, and background daemons are running.
3. **Inspect Radar Base Scan**: Check $0.5^\circ$ elevation scan for anomalous propagation clutter or beam blockage shadows along coastal or hill sectors.
4. **Review Preceding Shift Log**: Read all alerts issued, false alarm suppressions, or degraded mode declarations recorded in `audit_log` during the prior 12 hours.
5. **Acknowledge Watch Transfer**: Both incoming and outgoing forecasters sign the digital shift handover token in the console.

---

## 4. Alert Clearance & Human Oversight Workflow

When the system detects convective intensification, it automatically generates a **Draft CAP Bulletin**.

```
                           ALERT CLEARANCE FLOW
                           
     +---------------------------------------------------+
     | System Emits Draft Warning (Audible Tone + Banner)|
     +-------------------------+-------------------------+
                               |
                               v
     +---------------------------------------------------+
     | Forecaster Verification Checklist:                |
     | [x] Radar dBZ >= 40 (or VIL >= 20 kg/m²)          |
     | [x] Satellite Cloud Top < 220 K (Deep Convection) |
     | [x] Lightning Jump corroborated by Radar Core     |
     | [x] Warning Polygon covers correct urban zones    |
     +-------------------------+-------------------------+
                               |
              +----------------+----------------+
              |                                 |
              v                                 v
    [ VERIFIED ACCURATE ]             [ CLUTTER / FALSE ALARM ]
              |                                 |
              v                                 v
     +-------------------+             +-------------------+
     | Click [APPROVE]   |             | Click [DISMISS]   |
     | - Enter Passcode  |             | - Select Reason:  |
     | - Dispatches CAP  |             |   "AP Clutter",   |
     |   to NDMA / Web   |             |   "Decaying Cell" |
     +-------------------+             +-------------------+
```

### 4.1 Level Yellow (Advisory)
- **Visual**: Yellow boundary outline on map.
- **Action**: Passive monitoring. No siren. Ensure aviation and transport dispatchers have visibility of developing rain bands.

### 4.2 Level Orange (Severe Thunderstorm Warning)
- **Visual**: Flashing orange polygon; audible warning chime.
- **Forecaster Action**: Mandatory review within 3 minutes.
  1. Inspect radar core and trend.
  2. If cell is intensifying, click **[APPROVE & DISPATCH]**.
  3. Enter forecaster PIN.
  4. System transmits CAP XML to State Disaster Management Authority and updates public portal.

### 4.3 Level Red (Extreme Convective Hazard / Siren Clearance)
- **Visual**: Screen takeover, red strobe border, urgent klaxon audio.
- **Trigger**: $\ge 50\text{ dBZ}$, severe lightning jump ($\ge 30\text{ flashes/min}$), downburst/squall signatures.
- **Clearance Protocol**: **DUAL-KEY AUTHORIZATION REQUIRED**.
  1. Duty Forecaster reviews cell and initiates clearance request.
  2. Senior Lead Meteorologist (or secondary forecaster) reviews radar cross-section and enters secondary authorization key.
  3. Once dual-signed, siren relays at coastal towers / municipal zones are engaged and mobile emergency push notifications are dispatched.

---

## 5. Master Emergency Siren Kill Switch

If an erroneous alert is dispatched, an unvalidated siren sounds, or a false alarm loop develops:
1. **Immediate Action**: Hit the large pulsing red **[EMERGENCY SIREN KILL SWITCH]** button located on the top right navigation bar of the console.
2. **Result**:
   - Sends instantaneous hardware kill signal to all siren controllers ($< 1.0\text{ second}$).
   - Transmits CAP `status: Cancel` broadcast across all digital channels.
   - Puts Alert Service into `MUTED` status.
3. **Post-Action**: Call State Disaster Emergency Operations Centre (EOC) on the direct hotline to verbally confirm siren shutdown. Complete incident report within 2 hours.

---

## 6. How to Identify False Alarms & Anomalous Propagation

| Visual Signature | Meteorological Thunderstorm | Anomalous Propagation (AP) Ground Clutter |
|:---|:---|:---|
| **Motion** | Advects coherently with mid-level steering winds ($15\text{--}40\text{ km/h}$). | Completely stationary; anchored to coastline or hills. |
| **Doppler Radial Velocity ($V_r$)** | High velocity ($> 10\text{ m/s}$), distinct shear / convergence. | Near zero ($V_r \approx 0.0\text{ m/s}$) across the entire echo. |
| **Satellite Cloud Top** | Deep cold cloud shield ($T_B < 220\text{ K}$, often $< 205\text{ K}$). | Clear air or warm surface temperature ($T_B > 280\text{ K}$). |
| **Lightning Activity** | Active lightning strikes clustered under highest reflectivity core. | Zero lightning strikes recorded by Blitzortung network. |
| **Vertical Structure (VIL)** | High VIL ($> 20\text{ kg/m}^2$); echo tops $> 10\text{ km}$. | Extremely shallow echo; zero VIL; echo tops $< 2.5\text{ km}$. |

**Forecaster Action on AP Clutter**: Click **[SUPPRESS AP CLUTTER]** on the toolbar and drag a box over the false echo. The echo is instantly masked from the nowcast engine.

---

## 7. Interpreting Deep Learning Model Forecasts

Understanding the strengths and weaknesses of the **ResAtt-ConvLSTM2D** model (`convlstm_real_best.keras`):

### What the Model Does Well
- **Advective Trajectory**: Accurately projects the directional movement and translational velocity of widespread stratiform rain bands and mesoscale convective systems up to $+30$ minutes.
- **Domain Stability**: Low domain-wide error ($MAE \approx 0.467\text{ dBZ}$); never produces unphysical explosive blow-ups of false reflectivity in clear-air regions.

### What the Model Does Poorly (Known Failure Modes)
- **Spatial Smoothing of Convective Cores**: Due to MSE optimization, the model dampens intense $55\text{ dBZ}$ cores down to $20\text{--}25\text{ dBZ}$ at $+45\text{m}$ and $+60\text{m}$. **Do not assume a storm is dissipating merely because the model nowcast appears blurry or less intense at $+60\text{m}$!**
- **Convective Initiation**: The model cannot predict new convective cells before the first radar echo appears. Always monitor satellite 10.8 µm cloud-top cooling trends ($-5\text{ K}$ per 15 min indicates imminent updraft breakthrough).

---

## 8. Emergency Contacts & Escalation Directory

| Role / Entity | Contact Protocol | Escalation Threshold |
|:---|:---|:---|
| **Senior Lead Meteorologist** | Ext. 401 / Direct Radio Channel 1 | Level Red Siren clearance, conflicting radar interpretation. |
| **Radar Maintenance Engineer** | Ext. 405 / Mobile +91-XXXX-XXXXXX | DWR hardware outage $> 15\text{ minutes}$, STALO phase unlocked. |
| **MLOps & Systems Engineer** | Ext. 412 / On-call Pager | API HTTP 503 errors, database lockups, host memory alarms. |
| **State Disaster Control Room** | Dedicated Hotline / Red Phone | Level Red emergency clearance or Kill Switch activation. |

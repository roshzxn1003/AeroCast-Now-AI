# Atmospheric Data Quality Control & Cross-Sensor Consistency (Phase 9)

## 1. Multi-Stage Atmospheric Quality Control
AeroCast-Now AI incorporates automated multi-stage physical meteorological quality control:

1. **Temporal Horizon Check**:
   - Rejects future timestamps ($> 60\text{s}$ ahead of system clock) -> `INVALID`.
   - Flags stale observations ($> 60\text{ minutes}$ old) -> `STALE`.
2. **Geographic Domain Boundary**:
   - Enforces bounding coordinate box for India and surrounding waters ($6.0^\circ\text{N} - 38.0^\circ\text{N}$, $68.0^\circ\text{E} - 98.0^\circ\text{E}$).
3. **Physical Atmospheric Limits**:
   - Radar Reflectivity: $[-10.0, 75.0]\text{ dBZ}$
   - Vertically Integrated Liquid (VIL): $[0.0, 80.0]\text{ kg/m}^2$
   - Brightness Temperature (TIR): $[-95.0, 45.0]^\circ\text{C}$
   - Lightning Flash Density: $[0.0, 100.0]\text{ flashes/km}^2$
   - Lightning Flash Rate: $[0.0, 600.0]\text{ flashes/min}$
   - CAPE: $[0.0, 7500.0]\text{ J/kg}$
   - CIN: $[-800.0, 50.0]\text{ J/kg}$
   - Lifted Index: $[-16.0, 15.0]^\circ\text{C}$
4. **Cross-Sensor Physical Consistency**:
   - **dBZ vs VIL**: High VIL ($> 15\text{ kg/m}^2$) requires significant reflectivity ($> 30\text{ dBZ}$). Discrepancies indicate ground clutter or sensor miscalibration.
   - **dBZ vs TIR**: Reflectivity $\ge 45\text{ dBZ}$ (severe convection) must correlate with cold cloud-top temperatures ($\le -20.0^\circ\text{C}$).
   - **dBZ vs Lightning**: Rapid lightning flash rate jumps ($> 20\text{ fpm}$) without radar reflectivity ($< 20\text{ dBZ}$) trigger anomaly flags.

## 2. Standardized Quality Status Codes
- `VALID`: Authentic observation passing all numerical and physical checks.
- `SUSPECT`: Boundary violation or proxy estimation, usable with caution.
- `ESTIMATED`: Bounded forward-filled or climatologically imputed data.
- `STALE`: Outdated observation beyond expected refresh window.
- `MISSING`: No data available across observation window.
- `INVALID`: Unphysical reading, sensor noise, or future timestamp.

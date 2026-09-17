# Event-Based Storm Verification & Root-Cause Diagnostics — AeroCast-Now AI

## 1. Convective Event Verification Overview
In addition to grid-level continuous metrics, operational meteorologists evaluate forecasts by **Storm Events**:
* Did the model anticipate the initiation of a convective cell?
* How many minutes in advance was the first warning issued (Detection Lead Time)?
* What was the geographic spatial displacement (Location Error in km)?

---

## 2. Event Verification Metrics
Stored in the `storm_events` table:

1. **Classification**:
   * `DETECTED`: Storm observed and successfully forecast within spatial tolerance ($< 50\text{ km}$) and temporal window ($\pm 30\text{ min}$).
   * `MISSED`: Convective cell observed ($\ge 40\text{ dBZ}$ / lightning jump) but no forecast issued.
   * `FALSE_ALARM`: Storm predicted by model, but no corresponding reflectivity or lightning observed.
2. **Geographic Centroid Error**:
   * Computed via Haversine distance between predicted storm center $(lat_p, lon_p)$ and observed radar centroid $(lat_o, lon_o)$:
   $$d = 2 R \arcsin \left( \sqrt{ \sin^2\left(\frac{\Delta \phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta \lambda}{2}\right) } \right)$$
3. **Detection Lead Time**:
   * $\text{Lead Time} = T_{\text{first\_observed\_strike}} - T_{\text{first\_model\_alert}}$ (in minutes).

---

## 3. False Alarm & Miss Root-Cause Taxonomy
Every unverified or missed storm is categorized into standardized diagnostic causes:

| False Alarm Root Cause | Meteorological Description |
|---|---|
| `weak_convection` | Sub-severe cumulus congestus that lacked vertical growth or electrification. |
| `rapid_storm_dissipation` | Entrainment of mid-level dry air caused rapid cell collapse. |
| `data_quality_problem` | Radar clutter, AP (Anomalous Propagation), or anomalous AWS spikes. |
| `observation_gap` | AWS offline or radar beam blockage prevented observation capture. |
| `model_error` | Genuine false forecast resulting from over-sensitive convective parameterization. |
| `boundary_condition_error`| Numerical boundary moisture advection discrepancy. |

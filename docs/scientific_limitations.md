# Scientific & Physical Limitations Report

**System**: AeroCast-Now AI  
**Document ID**: DOC-SCI-001  
**Status**: ACTIVE / EVIDENCE-BASED  
**Date**: September 17, 2026  
**Audience**: Atmospheric Scientists, Operational Forecasters, System Architects, Evaluators  

---

## 1. Executive Summary

Operational weather prediction and artificial intelligence nowcasting systems are subject to fundamental atmospheric physics constraints, observational instrument limitations, and mathematical optimization trade-offs. 

In strict adherence to the **Phase 13 Scientific Acceptance Mandate**, this document presents a transparent, unvarnished inventory of the known physical, observational, and computational limitations of the **AeroCast-Now AI v1.0.0** platform.

Under no operational circumstances should AeroCast-Now AI outputs be interpreted as infallible physical simulations. Forecasters must evaluate all guidance through the lens of these documented constraints.

---

## 2. Atmospheric Scale & Spatial Resolution Constraints

### 2.1 The Mesoscale vs. Microscale Gap
- **Grid Resolution**: The standardized regional analysis grid spans $2.5^\circ \times 2.5^\circ$ ($64 \times 64$ pixels), yielding an effective horizontal spatial resolution of:
  $$\Delta x \approx 4.3\text{ km}, \quad \Delta y \approx 4.3\text{ km}$$
- **Physical Atmospheric Scales**:
  - Deep convective updraft cores typically measure **$1\text{ to }3\text{ km}$** in diameter.
  - Microbursts, dry downbursts, and gust front wind shears originate on scales of **$< 1\text{ km}$** and evolve over lifetimes of **$5\text{ to }15\text{ minutes}$**.
  - Severe tornadic vortices and mesocyclones measure **$< 500\text{ meters}$**.
- **Consequence**: The $4.3\text{ km}$ grid resolution **cannot resolve individual convective updraft towers**. It represents an area-averaged bulk reflectivity. High-gradient localized downburst winds cannot be deterministically resolved; they can only be statistically inferred from area-wide reflectivity and VIL proxies.

### 2.2 Temporal Sampling Cadence
- Observations and forecasts are structured at a **15-minute cadence** ($t-45, t-30, t-15, t_0 \rightarrow t+15, t+30, t+45, t+60$).
- Highly explosive convective initiation (e.g. severe pre-monsoon heat thunderstorms / "Nor'westers") frequently transitions from clear-air to $> 50\text{ dBZ}$ with active lightning in **under 10 minutes**.
- A 15-minute sampling cadence is fundamentally aliased with respect to the fastest explosive convective initiation lifecycles.

---

## 3. Doppler Weather Radar (DWR) Physical Artifacts

```
                       DWR RADAR GEOMETRIC LIMITATIONS
                       
     Cone of Silence
         \  |  /
          \ | /
           \|/
      +-----------+           Earth Curvature & Beam Broadening
      | Radar DWR | ~ ~ ~ ~ ~ ~ - - - - - _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
      +-----------+                                                     \
      ================================================================== \
            0 km                      100 km                    250 km    v
                                                              (Beam Shoots
                                                               Over Surface)
```

### 3.1 Beam Broadening and Earth Curvature
- Radar beams diverge at an angle of $\theta_{3dB} \approx 1.0^\circ$.
- At a range of $100\text{ km}$, the beam width is approximately $1.75\text{ km}$.
- At a range of $200\text{ km}$ (the outer boundary of the Chennai DWR domain), the beam width expands to **$3.5\text{ km}$**, and Earth curvature elevates the center of the lowest elevation scan ($0.5^\circ$) to approximately **$3,000\text{ meters above ground level}$**.
- **Consequence**: Radar scans at long ranges cannot observe low-level boundary layer moisture convergence or shallow surface precipitation. A severe shallow squall line may pass beneath the beam undetected at ranges $> 180\text{ km}$.

### 3.2 Cone of Silence
- Directly above the radar antenna (elevation angles $> 20^\circ$), mechanical tilt limits create a conical blind zone ("Cone of Silence") with a diameter of approximately $10\text{--}15\text{ km}$.
- Storms passing directly over the radar station experience an apparent sudden drop in echo tops and total volume reflectivity.

### 3.3 Anomalous Propagation (AP) and Sea Clutter
- Under nocturnal radiation inversions or strong marine boundary layer temperature inversions common along the Bay of Bengal coast, the radar beam bends downward more sharply than normal (super-refraction) and strikes the ocean or terrain.
- This creates intense false reflectivity returns ($40\text{--}60\text{ dBZ}$) with near-zero Doppler radial velocity ($V_r \approx 0.0\text{ m/s}$).
- While AeroCast-Now deploys velocity variance filtering (SOP-004), strong multi-path AP echoes can intermittently trigger false alarm convective initiation warnings if not cross-validated with satellite cloud-top data.

### 3.4 Precipitation Path Attenuation
- While S-band radars (such as Chennai DWR) experience minimal attenuation in rain compared to C-band or X-band radars, heavy hail cores or extreme tropical downpours ($> 80\text{ mm/hr}$) produce non-zero two-way attenuation, causing radar echoes located downrange behind severe storm cells to appear artificially dampened.

---

## 4. Satellite (INSAT-3D/3DR) Geostationary Constraints

### 4.1 Parallax Displacement Error
- INSAT-3D/3DR is located in geostationary orbit over the equator ($74^\circ\text{E}$ and $82^\circ\text{E}$).
- For targets at Chennai's latitude ($13.0^\circ\text{N}$), deep convective clouds reaching tropopause altitudes ($14\text{ to }16\text{ km}$) are observed at an oblique viewing angle.
- **Consequence**: High cloud-top anvils appear horizontally displaced northward and eastward by **$5\text{ to }10\text{ km}$** relative to their true surface rain cores. Without automated parallax correction, satellite cold cloud tops do not perfectly align with surface radar reflectivity cores.

### 4.2 Anvil Cirrus Masking
- The thermal infrared (TIR) channel measures the temperature of the highest opaque cloud surface.
- Extensive, high-altitude cirrus anvil shields generated by mature multicell storms obscure developing convective towers underneath. A new updraft initiating below an old anvil cannot be detected by satellite TIR until it punches through the cirrus deck as an overshooting top.

---

## 5. Lightning Network Physical Limits

### 5.1 Cloud-to-Ground (CG) vs. Total Lightning
- The Blitzortung community network operates in the Very Low Frequency (VLF, $3\text{--}30\text{ kHz}$) and Low Frequency (LF, $30\text{--}300\text{ kHz}$) radio spectrum.
- VLF/LF Time-of-Arrival (TOA) sensors primarily detect high-current **Cloud-to-Ground (CG)** return strokes (typical currents $10\text{--}100\text{ kA}$).
- However, during the early rapid intensification phase of severe thunderstorms, **Intra-Cloud (IC)** lightning surges precede CG strikes by **$10\text{ to }20\text{ minutes}$**.
- Because VLF sensors have lower detection efficiency for low-current IC pulses compared to VHF total lightning systems (e.g. EarthNetworks or spaceborne GLM/LIS), the empirical lead time of the lightning jump algorithm may be shortened from theoretical maximums ($25\text{ min}$) to $10\text{--}15\text{ min}$ during certain storm regimes.

### 5.2 Sensor Network Geometry & Detection Efficiency
- Blitzortung detection efficiency is non-uniform across the domain. Detection efficiency is highest over land within the sensor baseline and drops over the open Bay of Bengal where receiver stations are sparse.

---

## 6. Machine Learning Architecture & Optimization Constraints

### 6.1 Severe Class Imbalance & MSE Smoothing
- In the real historical atmospheric dataset (464 training sequences, 2,648 unseen test sequences), severe convective cells ($\ge 35\text{ dBZ}$) occupy **less than 1.5% of total grid cells**.
- The neural network was optimized using Mean Squared Error ($\mathcal{L}_{MSE}$).
- **Mathematical Failure Mode**: When convective storm trajectories exhibit spatial uncertainty, the minimum MSE is achieved by predicting the spatial conditional mean. The model predicts a blurry, smoothed reflectivity field where sharp convective peaks ($55\text{ dBZ}$) are dampened to $< 25\text{ dBZ}$.
- **Empirical Reality**: On real-world validation data, the model achieved continuous $MAE = 0.467\text{ dBZ}$, but **$CSI = 0.000$ and $POD = 0.000$ at the $35\text{ dBZ}$ severe storm threshold**.

```
True Atmospheric Field (Sharp Core):      MSE Model Forecast (Smoothed Blurry):
[ 0   0   0   0   0 ]                     [ 0   0   0   0   0 ]
[ 0  15  35  15   0 ]                     [ 0   8  14   8   0 ]
[ 0  35  58  35   0 ]   ------------->    [ 0  12  21  12   0 ]   (Peak 21 dBZ < 35 dBZ)
[ 0  15  35  15   0 ]                     [ 0   8  14   8   0 ]   (Result: Zero Hits!)
[ 0   0   0   0   0 ]                     [ 0   0   0   0   0 ]
```

### 6.2 Violation of Physical Conservation Laws
- Deep Learning architectures (ConvLSTM2D) do not embed Navier-Stokes equations, mass conservation, or thermodynamic moisture balance.
- As a consequence, predicted reflectivity fields can:
  - Spontaneously gain or lose total domain reflectivity mass across time steps.
  - Form unphysical discontinuous reflectivity gradients along image boundaries.
  - Fail to enforce physical advection dynamics under strong directional wind shear.

### 6.3 Progressive Lead Time Decay
- Predictability degrades rapidly with lead time due to atmospheric chaos:
  - At $+15\text{ min}$: Mean centroid error is $3.82\text{ km}$ (within grid cell resolution).
  - At $+60\text{ min}$: Mean centroid error expands to $19.85\text{ km}$, and peak reflectivity is dampened by $-68.3\%$.
- Forecasts beyond $+30\text{ minutes}$ provide general synoptic/mesoscale directional trend guidance only, not pinpoint parcel-level warnings.

---

## 7. Operational Mitigation Strategies

To counteract these scientific limitations in operational deployment:
1. **Mandatory Human-in-the-Loop**: Forecasters must cross-examine model outputs against raw, un-interpolated single-tilt radar PPI and Doppler velocity scans.
2. **Multi-Sensor Rule Gating**: Alerts require multi-sensor concordance (Radar VIL + Satellite Cloud Top + Lightning Jump).
3. **Explicit Uncertainty Visualization**: Dashboard renders spatial uncertainty buffers around $+30\text{m}$ to $+60\text{m}$ forecast centroids.
4. **Active Research Roadmap**: Phase 14 development will transition the neural core to Conditional Diffusion / Generative Adversarial architectures with Focal Loss to eliminate MSE-induced spatial smoothing.

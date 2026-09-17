# Uncertainty Quantification and Forecast Calibration Report

**System**: AeroCast-Now AI  
**Document ID**: DOC-VAL-006  
**Status**: ACTIVE / EVIDENCE-BACKED  
**Date**: September 17, 2026  
**Audience**: Atmospheric Scientists, Verification Engineers, Operational Duty Forecasters  

---

## 1. Executive Summary

In atmospheric nowcasting, communicating forecast uncertainty and maintaining calibrated probabilities is critical for preventing both over-warning (false alarm complacency) and under-warning (missed convective initiation). 

This document evaluates the uncertainty characteristics, calibration profile, and probabilistic limitations of the **AeroCast-Now AI v1.0.0** nowcasting platform. The platform operates a deterministic Deep Learning core (**ResAtt-ConvLSTM2D**) augmented by multi-sensor heuristic confidence scoring. 

### Key Findings
1. **Deterministic Core**: The current neural architecture (`convlstm_real_best.keras`) is a deterministic single-point spatio-temporal regression model. It does **not** natively sample from an ensemble distribution or compute Bayesian posterior weight distributions.
2. **Spatial Smoothing & Uncertainty Dilation**: Forecast variance diminishes and spatial smoothing increases monotonically with lead time ($t+15$ min to $t+60$ min). High-frequency convective details are smoothed into diffuse lower-reflectivity fields due to Mean Squared Error (MSE) loss minimization under spatial positional uncertainty.
3. **Absence of Calibrated Conformal Prediction**: While the operational alert engine applies empirical confidence weighting across radar, satellite, and lightning observations, the system does **not** yet provide formal conformal prediction intervals or calibrated Brier scores for pixel-level dBZ thresholds.
4. **Uncertainty Classification**: The system is classified as **DETERMINISTIC WITH MULTI-SENSOR HEURISTIC CONFIDENCE GATING**. It is **not** an ensemble prediction system (EPS).

---

## 2. Model Architecture & Uncertainty Nature

### 2.1 Deterministic Point Prediction Architecture
The production model uses Residual Attention ConvLSTM2D units:
- Input: 4 sequential frames of 3 channels (Radar dBZ, Satellite TIR brightness temperature, Lightning flash density) sampled at 15-minute intervals ($t-45, t-30, t-15, t_0$).
- Output: 4 sequential forecast frames for lead times $+15, +30, +45, +60$ minutes.
- Parameter Count: 191,524 trainable weights.
- Loss Function: Domain-wide Mean Squared Error ($\mathcal{L}_{MSE} = \frac{1}{N} \sum (y - \hat{y})^2$).

Because MSE penalizes large errors quadratically, whenever the model cannot resolve the exact advective path or cell life cycle of convective cores, the mathematically optimal strategy for minimizing MSE is to predict the conditional spatial expectation—effectively averaging all plausible storm trajectories. This produces progressive spatial blurring and dampens convective peaks.

### 2.2 Empirical Spread vs. Horizon
Across the 2,648 unseen real-world test sequences, the empirical error distributions dilate significantly across forecast horizons:

| Horizon | Mean Domain MAE (dBZ) | Max Absolute Cell Error (dBZ) | Mean Centroid Error (km) | Spatial Peak Dampening Ratio |
|:---:|:---:|:---:|:---:|:---:|
| **+15 min** | 0.407 dBZ | 28.4 dBZ | 3.82 km | -18.2% |
| **+30 min** | 0.449 dBZ | 33.1 dBZ | 7.45 km | -39.4% |
| **+45 min** | 0.485 dBZ | 36.8 dBZ | 12.90 km | -54.7% |
| **+60 min** | 0.525 dBZ | 41.2 dBZ | 19.85 km | -68.3% |

*Evidence File*: `docs/acceptance/evidence/model_validation_evidence.json`

---

## 3. Multi-Sensor Confidence Scoring Mechanism

To compensate for the lack of Bayesian probabilistic weights inside the neural network, the AeroCast-Now inference pipeline computes a composite **Forecast Confidence Index ($C_{nowcast} \in [0.0, 1.0]$)** derived from observational agreement and sensor health.

### 3.1 Mathematical Formulation
The composite confidence $C_{nowcast}$ at valid time $t$ is defined as:

$$C_{nowcast} = w_{rad} \cdot S_{rad} + w_{sat} \cdot S_{sat} + w_{ltg} \cdot S_{ltg} - \Delta_{latency} - \Delta_{leadtime}$$

Where:
- $S_{rad}$: Doppler Radar data quality score $[0, 1]$ (based on clutter ratio and beam blockage index).
- $S_{sat}$: INSAT-3D/3DR TIR thermal consistency score $[0, 1]$ (cloud-top brightness temperature $T_B < 220\text{ K}$).
- $S_{ltg}$: Lightning sensor temporal synchronization flag (1.0 if feed active within last 60s; 0.3 if stale; 0.0 if circuit breaker open).
- $w_{rad} = 0.50, w_{sat} = 0.30, w_{ltg} = 0.20$: Baseline observational weighting.
- $\Delta_{latency}$: Observation age penalty ($0.05$ per 5 minutes beyond scheduled radar cycle).
- $\Delta_{leadtime}$: Horizon penalty ($0.00$ at $+15$m; $0.08$ at $+30$m; $0.16$ at $+45$m; $0.25$ at $+60$m).

### 3.2 Confidence Calibration & Decision Bands

| Confidence Level ($C_{nowcast}$) | Operational Meaning | System Action |
|:---:|:---|:---|
| **$0.80 - 1.00$** | **HIGH** — All 3 sensors active, radar uncluttered, fresh timestamps. | Full graphical display; automated draft bulletin generated for forecaster signature. |
| **$0.50 - 0.79$** | **MODERATE** — Satellite/Radar latency elevated or minor clutter detected. | UI displays amber confidence banner; forecaster must verify raw radar scan. |
| **$0.30 - 0.49$** | **LOW / UNCERTAIN** — Radar offline (satellite proxy active) or severe lag. | Automated alert suppression active; nowcasts watermarked as "EXPERIMENTAL / LOW CONFIDENCE". |
| **$< 0.30$** | **REJECTED / UNRELIABLE** — Multi-sensor outage or unphysical inputs. | Pipeline aborts output generation; fallback to persistence bulletin; incident logged. |

---

## 4. Probabilistic Verification & Reliability Analysis

### 4.1 Brier Score Assessment
When evaluating continuous reflectivity forecasts against severe thunderstorm thresholds ($\ge 35$ dBZ and $\ge 45$ dBZ) across the 2,648 historical validation frames:

- **Brier Score at 35 dBZ**: $BS = 0.0142$
- **Brier Climatology Score ($BS_{clim}$)**: $0.0143$
- **Brier Skill Score ($BSS = 1 - \frac{BS}{BS_{clim}}$)**: $+0.007$ (Marginal skill over sample climatology)

*Interpretation*: The low raw Brier Score ($0.0142$) is an artifact of severe class imbalance (convective storms occupy $< 1.5\%$ of the total spatiotemporal grid volume). The Brier Skill Score reveals that the deterministic model's raw thresholding possesses virtually zero statistical skill over climatology in probability space, directly mirroring the Critical Success Index ($CSI = 0.000$) observed at the 35 dBZ threshold.

### 4.2 Reliability Curve Profile
A standard reliability diagram plots forecast probability bins on the horizontal axis against observed relative frequency on the vertical axis.
- In AeroCast-Now AI v1.0.0, because the model outputs deterministic float values rather than calibrated probabilities, computing a reliability curve requires binning heuristic confidence values against storm occurrence.
- **Under-confidence in Clear Air**: The model correctly predicts zero convection with $> 99.8\%$ true negative rate.
- **Severe Under-forecasting in Convective Peaks**: The model fails to emit probabilities above $0.50$ for severe convective cells because MSE pulls cell cores down toward background values.

---

## 5. Known Limitations & Edge Cases

1. **Rapid Orographic Triggering**: In complex terrain (e.g., Western Ghats or Himalayan foothills), convective initiation occurs on scales $< 5$ minutes. A deterministic 15-minute cadence model cannot quantify initiation probability before the first radar echo is detected.
2. **Convective Cell Mergers and Splits**: When two multicell storms merge, the deterministic ConvLSTM2D cannot represent the bimodal spatial probability distribution; it predicts an unphysical smeared centroid between the two actual cells.
3. **Deterministic False Precision**: A single reflectivity map at $+60$ min gives users a misleading visual impression of pinpoint spatial accuracy. Operational displays **must** render a spatial uncertainty cone or boundary buffer around detected centroids.

---

## 6. Recommendations for Phase 14 / Version 2.0 Roadmap

1. **Monte Carlo Dropout & Deep Ensembles**: Implement epistemic uncertainty quantification by enabling active dropout layers during inference, generating a 20-member nowcast ensemble.
2. **Diffusion / Generative Models**: Transition from MSE-minimized regression to generative diffusion models (e.g., conditional Latent Diffusion) to preserve high-frequency spatial gradients and prevent spatial blurring.
3. **Conformal Risk Control**: Implement inductive conformal prediction to produce guaranteed coverage intervals (e.g., 90% confidence bounding boxes for storm centroids).
4. **Isotonic Regression Calibration**: Fit post-hoc Platt scaling or Isotonic Regression on historical validation events to transform composite confidence scores into true frequentist probabilities of severe weather.

---

## 7. Conclusion & Governance Mandate

AeroCast-Now AI v1.0.0 provides valuable deterministic spatio-temporal guidance and heuristic multi-sensor confidence tracking. However, **it does not constitute a certified probabilistic forecasting system**. 

Under no operational circumstances shall deterministic model outputs be presented to civil authorities or the public as absolute, pinpoint spatial predictions beyond $+15$ minutes without explicit visualization of the $\pm 10\text{--}20\text{ km}$ positional uncertainty buffer.

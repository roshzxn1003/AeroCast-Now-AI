# AeroCast-Now AI: Neural Nowcaster Training & Verification Guide

This guide provides complete, step-by-step instructions on **how to train, evaluate, and deploy** the machine learning models that power AeroCast-Now AI Pro.

---

## 1. Model Architecture Overview

AeroCast-Now uses a custom **Residual-Attention Spatio-Temporal Convolutional LSTM (ResAtt-ConvLSTM2D)** network specifically engineered for ultra-fast, high-resolution precipitation and severe thunderstorm nowcasting (+15 to +120 minutes).

### Spatio-Temporal Tensor Specification
* **Domain Grid**: $32 \times 32$ spatial grid ($128\text{ km} \times 128\text{ km}$ radar domain, $4\text{ km}$ resolution).
* **Input Tensor ($\mathbf{X}$)**: Shape `(Batch, 4, 32, 32, 4)` spanning 4 consecutive 15-minute history frames ($t_{-45}, t_{-30}, t_{-15}, t_0$).
* **Target Tensor ($\mathbf{Y}$)**: Shape `(Batch, 4, 32, 32, 4)` spanning 4 forecast lead times ($t_{+15}, t_{+30}, t_{+45}, t_{+60}$).
* **Rollout**: For $+90$ min and $+120$ min, the engine performs auto-regressive recurrent rollout.

### 4 Physical Multimodal Channels
| Channel | Meteorological Sensor | Physical Quantity | Range & Normalization |
|---|---|---|---|
| **CH 0** | IMD Doppler Weather Radar (DWR) | Maximum Composite Reflectivity ($Z$) | $0 \le \text{dBZ} \le 75 \implies \hat{Z} = \frac{Z}{75}$ |
| **CH 1** | Radar Volume Scan Derived | Vertically Integrated Liquid (VIL) | $0 \le \text{VIL} \le 65\text{ kg/m}^2 \implies \widehat{\text{VIL}} = \frac{\text{VIL}}{65}$ |
| **CH 2** | INSAT-3D/3DR Geostationary Satellite | Thermal Infrared (TIR Channel 2) | $-85^\circ\text{C} \le \text{TIR} \le +35^\circ\text{C} \implies \widehat{\text{TIR}} = \frac{35 - \text{TIR}}{120}$ |
| **CH 3** | Blitzortung Lightning Detection Network | Cloud-to-Ground + Intra-Cloud Density | $0 \le \text{Flash} \le 25\text{ fpm/km}^2 \implies \widehat{F} = \frac{F}{25}$ |

---

## 2. Loss Function & Optimization

Meteorological radar data is severely imbalanced: clear air ($< 15\text{ dBZ}$) occupies $> 85\%$ of the domain, while dangerous convective cores ($\ge 35\text{ dBZ}$) occupy $< 5\%$. Standard MSE leads to blurry, washed-out forecasts that fail to predict thunderstorms.

AeroCast-Now uses a **Weighted Balanced Convective Loss**:

$$\mathcal{L}(Y, \hat{Y}) = \frac{1}{N} \sum_{i=1}^N \left( Y_i - \hat{Y}_i \right)^2 \times \left( 1.0 + 3.0 \cdot \mathbb{I}_{\{Y_i \ge \frac{35}{75}\}} \right)$$

This penalizes misses on dangerous storm cores with **$4\times$ weight**, forcing the neural network to preserve sharp squall boundaries and high reflectivity peaks.

---

## 3. How to Train the Model

### Prerequisites
Make sure you are in the project root directory with the Python virtual environment available:
```bash
cd /home/arun-roshan-gj/SIH
```

### Option A: Standard Full Training Run (Recommended)
Train for 18 epochs on 160 multi-modal convective sequences:
```bash
./train_models.sh --epochs 18 --samples 160 --batch-size 8
```
* **Execution Time**: ~3–5 minutes on modern CPU; < 40 seconds on NVIDIA GPU.
* **Output Checkpoint**: `backend/models/convlstm_nowcaster.keras`
* **Metadata & Metrics**: `backend/models/model_metadata.json`
* **Diagnostic Verification Curves**: `backend/models/training_performance.png`

### Option B: Quick Smoke Test (2 Epochs)
To quickly verify that the pipeline, TensorFlow, and loss functions run without errors:
```bash
./train_models.sh --epochs 2 --samples 16 --batch-size 4
```

### Option C: Train the 1D Multi-Parameter Weather LSTM
To train the baseline daily weather trend model (Temperature, Humidity, Pressure, Wind Speed, Cloud Cover):
```bash
./train_models.sh --weather-lstm
```

---

## 4. Meteorological Skill Verification Metrics

Upon completing training, `train_nowcasting_model.py` automatically evaluates standard World Meteorological Organization (WMO) verification scores on the held-out validation set:

1. **Critical Success Index (CSI / Threat Score)**:
   $$\text{CSI} = \frac{\text{Hits}}{\text{Hits} + \text{Misses} + \text{False Alarms}}$$
   * Measures accuracy penalizing both misses and false alarms. Production benchmark: $\text{CSI}_{35\text{dBZ}} \ge 0.82$.

2. **Probability of Detection (POD / Hit Rate)**:
   $$\text{POD} = \frac{\text{Hits}}{\text{Hits} + \text{Misses}}$$
   * Measures what fraction of real storm cores were successfully captured. Production benchmark: $\text{POD}_{35\text{dBZ}} \ge 0.88$.

3. **False Alarm Ratio (FAR)**:
   $$\text{FAR} = \frac{\text{False Alarms}}{\text{Hits} + \text{False Alarms}}$$
   * Measures false cry of wolf. Production benchmark: $\text{FAR}_{35\text{dBZ}} \le 0.10$.

4. **Heidke Skill Score (HSS)**:
   * Compares forecast skill against random chance ($-1$ to $+1$, where $1$ is perfect). Production benchmark: $\text{HSS} \ge 0.88$.

---

## 5. Live Runtime Integration

When you run `train_models.sh`:
1. The model weights are saved directly into `backend/models/convlstm_nowcaster.keras`.
2. The FastAPI backend (`backend/api_server.py`) automatically loads the updated model graph upon startup or hot-reload.
3. Every district nowcast (`/api/v1/districts/nowcast/{query}`) and national radar nowcast (`/api/nowcast`) immediately serves predictions from the newly trained weights.
4. The frontend Diagnostics screen (`More -> AI Model Architecture`) displays the updated parameters, training samples, and MAE/RMSE scores.

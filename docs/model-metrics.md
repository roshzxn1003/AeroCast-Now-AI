# Meteorological Verification Metrics — AeroCast-Now AI

## 1. Metric Taxonomy
Operational evaluation in AeroCast-Now AI strictly distinguishes between:
1. **Continuous Regression Metrics**: Tracking field-level reflectivity (dBZ), lightning flash rate density, and sounding thermodynamics.
2. **Categorical / Convective Event Metrics**: Derived from $2 \times 2$ contingency tables for convective thresholds ($\ge 35\text{ dBZ}$, $\ge 1\text{ flash/min}$).

---

## 2. Mathematical Formulations

### Categorical Contingency Matrix
Given Hit ($H$), False Alarm ($F$), Miss ($M$), and Correct Negative ($Z$):
* **Total Events**: $N = H + F + M + Z$

### Critical Success Index (CSI / Threat Score)
Measures the fraction of observed and/or forecast events that were correctly predicted, disregarding correct negatives:
$$\text{CSI} = \frac{H}{H + F + M}$$
* Range: $[0, 1]$; Perfect Score: $1.0$.

### Probability of Detection (POD / Hit Rate)
$$\text{POD} = \frac{H}{H + M}$$
* Range: $[0, 1]$; Perfect Score: $1.0$.

### False Alarm Ratio (FAR)
$$\text{FAR} = \frac{F}{H + F}$$
* Range: $[0, 1]$; Perfect Score: $0.0$.

### Frequency Bias (FBIAS)
$$\text{FBIAS} = \frac{H + F}{H + M}$$
* $\text{FBIAS} > 1$: Model over-forecasts convection.
* $\text{FBIAS} < 1$: Model under-forecasts convection.

### Heidke Skill Score (HSS)
Skill of the forecast relative to random chance:
$$\text{Expected Correct } (E) = \frac{(H + M)(H + F) + (Z + M)(Z + F)}{N}$$
$$\text{HSS} = \frac{(H + Z) - E}{N - E}$$
* Range: $[-\infty, 1]$; $>0$ indicates skill over random forecast; $1.0$ is perfect.

### Equitable Threat Score (ETS / Gilbert Skill Score)
$$\text{Random Hits } (H_r) = \frac{(H + M)(H + F)}{N}$$
$$\text{ETS} = \frac{H - H_r}{H + F + M - H_r}$$

---

## 3. Continuous Regression Metrics
* **Mean Absolute Error (MAE)**: $\frac{1}{n} \sum |y_i - \hat{y}_i|$
* **Root Mean Squared Error (RMSE)**: $\sqrt{\frac{1}{n} \sum (y_i - \hat{y}_i)^2}$
* **Mean Error (Bias)**: $\frac{1}{n} \sum (\hat{y}_i - y_i)$
* **Pearson Correlation Coefficient ($r$)**: Covariance of forecast and observation divided by product of their standard deviations.

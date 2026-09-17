# Model & Atmospheric Drift Monitoring — AeroCast-Now AI

## 1. Types of Drift in Atmospheric Nowcasting
Atmospheric systems undergo dramatic seasonal transitions (e.g., South-West Monsoon vs North-East Monsoon vs Pre-monsoon convection in Tamil Nadu).
AeroCast-Now AI tracks two distinct drift forms:
1. **Atmospheric Covariate Drift (Input Drift)**: Shifts in distribution of atmospheric features (CAPE, PWAT, Shear, Surface Temperature, Reflectivity).
2. **Concept Drift / Performance Degradation**: Changes in the meteorological relationship between radar echo trends and ground-strike lightning discharges, leading to degraded CSI and increased FAR.

---

## 2. Statistical Drift Detection Engines

### Population Stability Index (PSI)
Computed by segmenting the baseline reference distribution into 10 quantiles:
$$\text{PSI} = \sum_{k=1}^{10} \left( \text{Actual}_k - \text{Expected}_k \right) \times \ln\left(\frac{\text{Actual}_k}{\text{Expected}_k}\right)$$

* **$\text{PSI} < 0.10$**: Stable / No significant distribution change.
* **$0.10 \le \text{PSI} < 0.25$**: Moderate drift. Flag warning in operational dashboard.
* **$\text{PSI} \ge 0.25$**: Severe drift. Triggers automated retraining request candidate.

### Two-Sample Kolmogorov-Smirnov (KS) Test
Measures the maximum empirical divergence between reference training distributions and sliding 7-day inference distributions:
$$D = \sup_x |F_{\text{ref}}(x) - F_{\text{current}}(x)|$$

If $p\text{-value} < 0.01$, drift is flagged as statistically significant.

---

## 3. Multi-Dimensional Model Health Scorecard
AeroCast-Now AI aggregates six operational dimensions into an overall Health Index ($0$ to $100$):
1. **Verification Performance (CSI / POD)**: Weight $25\%$
2. **Input Covariate Stability (PSI / KS)**: Weight $20\%$
3. **Inference Latency & Sizing**: Weight $15\%$
4. **Data Pipeline Freshness & Gaps**: Weight $15\%$
5. **Artifact Integrity & Checksums**: Weight $15\%$
6. **False Alarm Ratio (FAR)**: Weight $10\%$

Status thresholds:
* $\ge 85$: `EXCELLENT`
* $70 - 84$: `HEALTHY`
* $50 - 69$: `WARNING`
* $< 50$: `CRITICAL` (Operator alerted; retraining investigation initiated)

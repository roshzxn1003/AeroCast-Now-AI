# Continuous Multi-Horizon Forecast Verification — AeroCast-Now AI

## 1. Principles of Operational Verification
Forecast verification operates strictly in retrospect:
$$\text{Verification Time } T_v = T_{\text{init}} + \Delta T_{\text{horizon}}$$

Observations are retrieved at $T_v$ and matched against the immutable prediction generated at $T_{\text{init}}$.

### Handling Missing Observations
Data dropouts, radar clutter maintenance, or AWS telemetry packet loss must **never** be counted as model forecast failures (such as zero reflection or zero lightning).
* If true observation data is unavailable or QC-flagged as `CORRUPT` at $T_v$, the verification engine flags `status = "UNAVAILABLE"`.
* Missing cases are excluded from categorical contingency tables and continuous error distributions, preventing artificial degradation of model skill scores.

---

## 2. Multi-Horizon Lead-Time Decomposition
AeroCast-Now AI continuously tracks skill degradation across discrete nowcasting horizons:
* **+15 minutes**: High skill, near-linear advection and initial storm cell development.
* **+30 minutes**: Convective initiation, lightning flash rate acceleration.
* **+45 minutes**: Non-linear merger, cell splitting, downburst initiation.
* **+60 minutes**: Maximum nowcasting horizon for convective extrapolation before numerical models dominate.
* **+90 / +120 minutes**: Experimental extended horizons.

Each verification record decomposes metrics by horizon in `multi_horizon_verifications`:
* Lead-time specific MAE, RMSE, Pearson Correlation, and Mean Bias.
* Lead-time specific Critical Success Index (CSI), Probability of Detection (POD), and False Alarm Ratio (FAR).

---

## 3. Database Persistence
Verifications are stored in `multi_horizon_verifications`:
```sql
CREATE TABLE multi_horizon_verifications (
    verification_id TEXT UNIQUE NOT NULL,
    forecast_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    horizon_minutes INTEGER NOT NULL,
    initialization_time TEXT NOT NULL,
    target_valid_time TEXT NOT NULL,
    mae REAL,
    rmse REAL,
    csi REAL,
    pod REAL,
    far REAL,
    hss REAL,
    ets REAL,
    status TEXT NOT NULL -- 'VERIFIED', 'UNAVAILABLE', 'FAILED'
);
```

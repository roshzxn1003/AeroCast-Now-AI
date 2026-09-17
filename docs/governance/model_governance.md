# Model Governance & Machine Learning Lifecycle Policy

**System**: AeroCast-Now AI  
**Document ID**: DOC-GOV-001  
**Status**: ACTIVE POLICY  
**Date**: September 17, 2026  
**Audience**: MLOps Engineers, Atmospheric Scientists, Model Review Committee  

---

## 1. Principles of Model Governance

In an operational meteorological AI system, uncontrolled model deployment can lead to catastrophic consequences: missed severe storm warnings or widespread false alarms that erode public trust. 

This policy establishes strict governance protocols for model artifact lineage, lifecycle phase transitions, cryptographic integrity checks, multi-stakeholder promotion approval, continuous drift monitoring, and emergency rollback procedures.

```
+-----------------------------------------------------------------------------------+
|                           MODEL LIFECYCLE STATE MACHINE                           |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  +--------------------+         +--------------------+                            |
|  |    EXPERIMENTAL    | ------> |     VALIDATION     |                            |
|  |  (Offline Research)|         | (Automated Testing)|                            |
|  +--------------------+         +---------+----------+                            |
|                                           |                                       |
|                                   [ Meets Criteria ]                              |
|                                           |                                       |
|                                           v                                       |
|                                 +--------------------+                            |
|                                 |     CANDIDATE      |                            |
|                                 | (Staged in Registry)                            |
|                                 +---------+----------+                            |
|                                           |                                       |
|                       [ Lead Met + MLOps Admin Signature ]                        |
|                                           |                                       |
|                                           v                                       |
|                                 +--------------------+                            |
|                 +-------------> |      APPROVED      | <---------+                |
|                 |               |  (Active in Prod)  |           |                |
|                 |               +---------+----------+           |                |
|                 |                         |                      |                |
|           [ Rollback ]              [ Deprecated ]          [ Hot Swap ]          |
|                 |                         |                      |                |
|                 |                         v                      |                |
|                 |               +--------------------+           |                |
|                 +-------------- |      RETIRED       | ----------+                |
|                                 |  (Archival Replay) |                            |
|                                 +--------------------+                            |
+-----------------------------------------------------------------------------------+
```

---

## 2. Model Lifecycle States

Every model artifact within the AeroCast-Now AI ecosystem must reside in exactly one of the following five lifecycle states:

| Lifecycle State | Permitted Operations | Serving Permissions | Storage Location |
|:---|:---|:---|:---|
| **`EXPERIMENTAL`** | Feature engineering, hyperparameter tuning, loss function ablation. | **Prohibited** from loading into API server. | Local researcher workspace / scratch. |
| **`VALIDATION`** | Execution of benchmark test suites (`test_real_validation.py`, baseline comparisons). | Staging test client only. | `models/validation/` |
| **`CANDIDATE`** | Pre-deployment stress testing, latency profiling, dual-key review. | Staging environment only. | `backend/models/candidates/` |
| **`APPROVED`** | Live nowcasting, REST API inference, forecaster dashboard serving. | **Authorized for Production**. | `backend/models/convlstm_real_best.keras` |
| **`RETIRED`** | Historical replay, model regression analysis, academic audits. | Read-only offline evaluation. | `models/archive/` |

---

## 3. SQLite Model Registry & Metadata Specification

All model versions are tracked in the `model_registry` relational database table (`data/aerocast.sqlite3`):

```sql
CREATE TABLE IF NOT EXISTS model_registry (
    model_id TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    architecture TEXT NOT NULL,
    weights_path TEXT NOT NULL,
    sha256_checksum TEXT NOT NULL,
    training_dataset_id TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('EXPERIMENTAL', 'VALIDATION', 'CANDIDATE', 'APPROVED', 'RETIRED')),
    registered_at TEXT NOT NULL,
    approved_by TEXT,
    approved_at TEXT,
    retirement_reason TEXT
);
```

### 3.1 Active Production Model Metadata Record
- **Model ID**: `convlstm_real_best`
- **Version**: `1.0.0`
- **Architecture**: `ResAtt-ConvLSTM2D`
- **Parameter Count**: 191,524 trainable parameters
- **Weights Checksum (SHA-256)**: `6194f04a8ae4756dca8bf11d4627c350873bec25c8ad20e0b0ca9137fc603e87`
- **Status**: `APPROVED` (Assistive / Human-in-the-Loop Mode)
- **Training Samples**: 464 historical temporal sequences (strictly partitioned)
- **Validation Samples**: 2,648 unseen historical sequences

---

## 4. Promotion Criteria & Approval Protocol

Promotion from `CANDIDATE` to `APPROVED` requires passing all empirical gating criteria:

### 4.1 Quantitative Quality Gates
1. **Continuous Domain Accuracy**: Test Mean Absolute Error ($MAE$) $\le 0.60\text{ dBZ}$ across all channels.
2. **Convective Skill Floor**: Critical Success Index ($CSI$) at $\ge 25\text{ dBZ}$ must exceed sample persistence baseline ($CSI > 0.05$).
3. **False Alarm Ratio Ceiling**: $FAR \le 0.45$ at $35\text{ dBZ}$.
4. **Numerical Stability**: Zero `NaN` or `Inf` outputs across 10,000 synthetic test tensor evaluations.
5. **Cold-Start Warmup Latency**: $< 2,000\text{ ms}$ on target production host CPU.

### 4.2 Multi-Stakeholder Dual-Key Approval
Promotion cannot be executed by an automated CI script. It requires authenticated digital signatures from two authorized roles:
1. **Lead Atmospheric Scientist**: Certifies that model predictions are physically realistic and advective fields do not exhibit non-physical mass destruction.
2. **Lead MLOps / Systems Engineer**: Certifies that memory footprint, thread safety, and inference latency comply with production SLAs.

```bash
# Production Promotion Command
PYTHONPATH=backend ./venv/bin/python scripts/promote_model.py \
  --model-id convlstm_candidate_v2 \
  --lead-met "Dr. S. Ramanathan" \
  --mlops-lead "A. Roshan" \
  --auth-key $PROMOTION_MASTER_TOKEN \
  --notes "Monsoon 2026 update with focal loss and lightning jump integration"
```

---

## 5. Model Monitoring & Drift Detection Policy

1. **Continuous Verification Cycle**: Every 24 hours, the system compares the previous day's $+15\text{m}, +30\text{m}, +45\text{m}, +60\text{m}$ forecast grids against verifying radar scans.
2. **Drift Alarm Thresholds**:
   - **Warning (Amber)**: Weekly mean MAE increases by $> 25\%$ above baseline ($> 0.65\text{ dBZ}$).
   - **Critical (Red)**: Convective cell detection drops to zero ($CSI = 0.000$) for 3 consecutive convective events, or spatial displacement error at $+30\text{m}$ exceeds $15\text{ km}$.
3. **Automated Drift Response**:
   - If Critical Drift is declared, the system automatically transitions model output to **Advisory Only Mode**, adjusts the UI confidence banner, and alerts the MLOps team.

---

## 6. Emergency Rollback Protocol

If a newly deployed model exhibits unpredicted production anomalies (e.g. memory leak, worker segfault, spatial explosion of false reflectivity), the on-duty operator must execute an immediate hot rollback:

```bash
# Emergency Model Rollback
PYTHONPATH=backend ./venv/bin/python scripts/rollback_model.py \
  --target-id convlstm_real_previous \
  --reason "Memory leak detected under high concurrent load" \
  --operator "duty-ops-01"
```

- **Rollback Latency**: $< 500\text{ ms}$ (memory hot-swap without dropping active HTTP connections).
- **Integrity Check**: Rollback target SHA-256 is verified before memory assignment.
- **Audit Logging**: Incident recorded in `audit_log` with operator ID, prior model ID, target model ID, and rationale.

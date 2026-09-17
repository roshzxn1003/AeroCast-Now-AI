# Model Lifecycle Governance — AeroCast-Now AI

## 1. Lifecycle Overview
In AeroCast-Now AI, every deep learning and statistical model moves through a strictly governed 7-stage lifecycle:
```
EXPERIMENTAL ──► CANDIDATE ──► VALIDATED ──► STAGING ──► PRODUCTION
                                                 │              │
                                                 ▼              ▼
                                              REJECTED       RETIRED
```

Under no circumstances is a model promoted automatically into `PRODUCTION`. Every transition is audited in SQLite (`model_actions` table) with immutable cryptographic checksums (SHA-256) and human actor attribution.

---

## 2. Stage Definitions

| Stage | Description | Gate / Prerequisite |
|---|---|---|
| `EXPERIMENTAL` | Research prototypes and exploratory architecture iterations. | Minimum code linting and reproducibility scripts. |
| `CANDIDATE` | Trained model checkpoint with fixed weights and hyperparameter receipts. | Successful training convergence on chronological training split. |
| `VALIDATED` | Evaluated against protected offline holdout test sets without data leakage. | Outperforms Persistence & Climatology; CSI $\ge 0.25$, POD $\ge 0.35$. |
| `STAGING` | Deployed in parallel shadow mode alongside production on live incoming observations. | 7-day shadow run; latency $< 250\text{ ms}$; zero uncaught inference exceptions. |
| `PRODUCTION` | Active model serving live forecasts, public bulletins, and civil protection alerts. | Explicit human approval by Senior Meteorologist or Lead MLOps Engineer. |
| `RETIRED` | Previous production models archived with preserved weights for instant rollback. | Replaced by a newly promoted model or manually decommissioned. |
| `REJECTED` | Candidate or Staged models that failed validation gates or degraded in shadow tests. | Detailed rejection rationale logged in `retraining_requests` and `model_actions`. |

---

## 3. Strict Chronological Train / Val / Test Partitioning
Atmospheric systems exhibit strong autocorrelation and seasonal regimes. Standard random k-fold cross-validation results in severe data leakage. AeroCast-Now AI enforces strict chronological partitioning:
1. **Training Set**: Historical observations preceding the validation horizon.
2. **Validation Set**: Intermediary chronological window used exclusively for early stopping and hyperparameter tuning.
3. **Protected Holdout Test Set**: A strictly quarantined future observation block that is **never** consumed during gradient updates, architecture search, or prompt engineering.

---

## 4. Model Identity & Cryptographic Integrity
Every model artifact registered into the system receives an immutable `ModelIdentity`:
* `model_id`: Canonical unique identifier (e.g. `convlstm_real_best`).
* `version`: Semantic versioning (e.g. `1.0.0`).
* `model_family`: Neural network family (`ResAtt-ConvLSTM2D`).
* `architecture_version`: Specification version (`2.0.0`).
* `training_dataset_version`: Exact training dataset snapshot tag (`2026.09.001`).
* `feature_pipeline_version`: Version of feature engineering code (`1.0.0`).
* `model_hash`: SHA-256 checksum computed over weights on disk.

On startup and prior to every inference batch, `ModelManager` verifies that `sha256(weights_file) == model_hash`. If a mismatch is detected, execution halts with `IntegrityError`.

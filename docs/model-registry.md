# Model Registry Architecture — AeroCast-Now AI

## 1. Registry Architecture
The AeroCast-Now AI Model Registry provides centralized versioning, metadata storage, artifact integrity checks, and promotion governance for all nowcasting models.

### Directory Organization
```
backend/models/
├── production/          # Currently active production weights (.keras)
├── staging/             # Candidates undergoing shadow validation
├── archive/             # Retired production models for fast rollback
├── convlstm_real_best.keras
└── model_metadata_real.json
```

---

## 2. SQLite Ledger Schema

The model registry is backed by SQLite Write-Ahead Logging (WAL) tables:
1. `model_registry`:
   * `model_id` (TEXT UNIQUE)
   * `version` (TEXT)
   * `stage` (`EXPERIMENTAL`, `CANDIDATE`, `VALIDATED`, `STAGING`, `PRODUCTION`, `RETIRED`, `REJECTED`)
   * `architecture` (TEXT)
   * `dataset_version` (TEXT)
   * `feature_version` (TEXT)
   * `weights_path` (TEXT)
   * `model_hash` (TEXT, SHA-256)
   * `is_active_production` (INTEGER: 0 or 1)
   * `metrics_json` (TEXT)
   * `limitations_json` (TEXT)
2. `model_artifacts`:
   * `artifact_id`, `model_id`, `version`, `file_path`, `file_hash`, `file_size_bytes`, `status` (`VALID`, `CORRUPT`, `MISSING`).
3. `model_actions`:
   * `action_id`, `model_id`, `version`, `action_type` (`REGISTER`, `PROMOTE`, `ROLLBACK`, `RETIRE`), `actor`, `reason`, `previous_state`, `new_state`, `details_json`.

---

## 3. Core Registry Python API
Located in [`backend/ml/model_registry.py`](file:///home/arun-roshan-gj/SIH/backend/ml/model_registry.py):

* `ModelRegistry.get_production_model()`: Fetches the current production model.
* `ModelRegistry.verify_artifact_integrity(model_id)`: Recomputes SHA-256 and records validation status.
* `ModelRegistry.register_candidate_model(...)`: Stages new weights and hashes into `staging/`.
* `ModelRegistry.promote_to_production(...)`: Executes promotion gates, archives existing model, and sets active flag.
* `ModelRegistry.rollback_production(...)`: Re-promotes previous production model with rollback audit logging.

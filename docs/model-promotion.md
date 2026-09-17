# Model Promotion Gates & Workflow — AeroCast-Now AI

## 1. Automated Promotion Gates
To transition a model from `STAGING` to `PRODUCTION`, the model must satisfy all non-negotiable gates:

1. **Cryptographic Checksum Verification**:
   * SHA-256 computed on disk must match the registry ledger. Status must be `VALID`.
2. **Protected Holdout Performance Gate**:
   * Critical Success Index (CSI) $\ge 0.25$ on convective thresholds ($\ge 35\text{ dBZ}$).
   * Probability of Detection (POD) $\ge 0.35$.
   * False Alarm Ratio (FAR) $\le 0.45$.
3. **Reference Baseline Outperformance**:
   * $\text{Skill Score vs. Persistence} > 0.0$.
   * $\text{CSI}_{\text{candidate}} > \text{CSI}_{\text{persistence}}$.
4. **Shadow Staging Stability**:
   * Zero unhandled exceptions or NaN gradient outputs during 7-day shadow scoring.
   * Batch inference latency within budget ($\le 250\text{ ms}$ on GPU, $\le 800\text{ ms}$ on CPU).
5. **Human Attribution Sign-Off**:
   * Promotion command must identify the authorized operator (`promoted_by`).

---

## 2. Promotion Sequence
When `ModelRegistry.promote_to_production(model_id, promoted_by)` executes:
1. Verify all quality gates.
2. Locate the existing active production model.
3. If an existing production model exists:
   * Demote its stage to `RETIRED`.
   * Set `is_active_production = 0`.
   * Move or copy its weights into `backend/models/archive/`.
4. Update candidate model in `model_registry`:
   * Set `stage = "PRODUCTION"`.
   * Set `is_active_production = 1`.
   * Record `promoted_at = now()` and `promoted_by`.
5. Copy candidate weights to `backend/models/production/`.
6. Record audit action in `model_actions` table.
7. Trigger `ModelManager` to hot-reload the new production weights into memory without application downtime.

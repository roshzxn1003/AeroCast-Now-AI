# Model Rollback Protocols — AeroCast-Now AI

## 1. Fast Rollback Architecture
If a newly deployed production model exhibits operational anomalies, severe false alarms during an unexpected convective outbreak, or latency spikes, operators can execute a single-command rollback.

AeroCast-Now AI maintains previous production artifacts in `backend/models/archive/` and records historical deployments in `model_actions`.

---

## 2. Rollback Execution
Rollback can be triggered via CLI or API:
```bash
# Python / CLI invocation
python -c "from ml.model_registry import model_registry; model_registry.rollback_production('convlstm_real_best', actor='ops_admin', reason='Spike in False Alarms')"
```

Or via API:
```http
POST /api/models/rollback
Content-Type: application/json

{
  "target_model_id": "convlstm_real_best",
  "actor": "ops_admin",
  "reason": "False alarms over Coastal Chennai"
}
```

---

## 3. Rollback Safety Guarantees
1. **Zero Downtime**: Active inference requests complete normally; subsequent requests transparently route to the rolled-back model weights.
2. **Artifact Integrity Pre-check**: Before switching, the rolled-back weights in `archive/` undergo SHA-256 integrity checks. If corrupted, the rollback is aborted.
3. **Audit Trail**: Action is recorded in `model_actions` with `action_type = 'ROLLBACK'`, capturing the actor, previous failed model, and incident rationale.

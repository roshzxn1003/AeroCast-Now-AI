# Operational Runbook: Production Model Rollback

## 1. When to Execute a Rollback
A production model rollback is justified when:
* Newly promoted model demonstrates a sudden spike in False Alarms ($\text{FAR} > 0.50$) during active convective outbreaks.
* Verification scores drop below the simple Persistence baseline ($\text{Skill Score} < 0$).
* The model produces repetitive numerical divergence exceptions or latency spikes ($> 800\text{ ms}$).

---

## 2. Pre-Rollback Confirmation
1. Verify who authorized the rollback and record the operational incident reason.
2. Confirm that the previous production weights file exists in `backend/models/archive/`.

---

## 3. Rollback Execution Commands

### Via REST API (Recommended):
```bash
curl -X POST "http://localhost:8000/api/system/model-registry/rollback?target_model_id=convlstm_real_best" \
     -H "X-API-Key: aerocast_admin_dev_token" | jq .
```

### Via Python CLI (Fallback):
```bash
python -c "
from ml.model_registry import ModelRegistry
from ml.model_manager import get_model_manager

reg = ModelRegistry()
res = reg.rollback_production_model(operator='admin_ops', reason='Spike in False Alarms')
if res.success:
    get_model_manager().load_active_production_model()
    print('Rollback successfully completed.')
else:
    print('Rollback failed:', res.message)
"
```

---

## 4. Post-Rollback Audit & Verification
1. Inspect the production model endpoint:
   ```bash
   curl -s http://localhost:8000/api/models/production | jq .
   ```
   * Confirm that `stage` is `PRODUCTION` and `model_hash` matches archive weights.
2. Verify audit trail in SQLite:
   ```sql
   SELECT * FROM model_actions WHERE action_type = 'ROLLBACK' ORDER BY id DESC LIMIT 1;
   ```
3. Monitor the `/ready` probe to ensure the restored model completes the warmup pass and achieves `READY` status.

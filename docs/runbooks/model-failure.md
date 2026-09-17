# Operational Runbook: Model Loading & Checksum Failure

## 1. Symptoms & Alert Trigger
* ModelManager status is `failed` or `uninitialized`.
* API startup fails with `OPERATIONAL INTEGRITY FAILURE: Model artifact integrity verification failed!`.
* `/ready` returns 503 with `"model_status": "failed"`.

---

## 2. Confirmation Steps
1. Query active production model status:
   ```bash
   curl -s http://localhost:8000/api/models/production | jq .
   ```
2. Manually compute SHA-256 over production weights:
   ```bash
   sha256sum backend/models/convlstm_real_best.keras
   ```

---

## 3. Diagnostic Checklist
* Has the model weights file been overwritten by an unverified process?
* Did an incomplete download or deployment copy corrupt the binary artifact?
* Does the weights file path point to a nonexistent directory?

---

## 4. Mitigation & Resolution
1. **Corrupt Weights**:
   Restore the genuine verified `.keras` weights from `backend/models/archive/` or secure remote S3 bucket.
2. **Instant Rollback**:
   Execute rollback to previous production checkpoint:
   ```bash
   curl -X POST "http://localhost:8000/api/system/model-registry/rollback?target_model_id=convlstm_real_best" \
        -H "X-API-Key: aerocast_admin_dev_token"
   ```

---

## 5. Recovery Verification
* Confirm `is_valid: true` in `curl -s http://localhost:8000/api/models/production`.
* Check warmup execution log: `model_warmup_completed` with `status: success`.

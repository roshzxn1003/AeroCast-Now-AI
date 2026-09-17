# Model Monitoring Operational Runbook — AeroCast-Now AI

## 1. Daily Monitoring Checklist

1. **Verify Production Model Health**:
   ```bash
   curl -s http://localhost:8000/api/models/production | jq .
   curl -s http://localhost:8000/api/models/convlstm_real_best/health | jq .
   ```
   * Ensure `health_index >= 70` and status is `HEALTHY` or `EXCELLENT`.
2. **Inspect Multi-Horizon Verification Trends**:
   ```bash
   curl -s "http://localhost:8000/api/verification/summary?hours=24" | jq .
   ```
   * Confirm CSI at +15m $\ge 0.35$ and at +60m $\ge 0.15$.
   * Confirm Skill Score vs Persistence $> 0.0$.
3. **Check Atmospheric Input Drift**:
   ```bash
   curl -s http://localhost:8000/api/models/convlstm_real_best/drift | jq .
   ```
   * If any atmospheric variable reports $\text{PSI} \ge 0.25$, inspect seasonal weather shift or sensor calibration drift.

---

## 2. Handling Operational Incidents

### Scenario A: Health Score Drops Below 50 (`CRITICAL`)
1. Inspect the 6 health components in the health API response.
2. If due to high FAR or low CSI:
   * Review recent storm events: `curl -s "http://localhost:8000/api/verification/events?classification=FALSE_ALARM" | jq .`
   * Check whether false alarms are due to radar clutter or genuine over-forecasting.
3. If necessary, execute a fast rollback:
   * Follow instructions in [docs/model-rollback.md](file:///home/arun-roshan-gj/SIH/docs/model-rollback.md).

### Scenario B: Artifact Checksum Failure on Startup
1. Review error logs: Look for `IntegrityError` or `status = CORRUPT`.
2. Check `model_artifacts` table:
   ```sql
   SELECT * FROM model_artifacts WHERE status = 'CORRUPT';
   ```
3. Re-stage genuine weights from trusted S3/remote storage or promotion backup directory `backend/models/staging/`.
4. Run `ModelRegistry.verify_artifact_integrity(model_id)` to clear the alert.

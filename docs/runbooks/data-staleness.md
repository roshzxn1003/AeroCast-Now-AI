# Operational Runbook: Data Staleness & Telemetry Gaps

## 1. Symptoms & Alert Trigger
* Ingestion fresh-data gate reports `overall_status: "stale"` or `"delayed"`.
* Frontend globe displays amber `STALE OBS` badge.
* Elapsed time since last radar volume scan $> 20\text{ minutes}$ or satellite frame $> 45\text{ minutes}$.

---

## 2. Confirmation Steps
1. Query data freshness API:
   ```bash
   curl -s http://localhost:8000/data/freshness | jq .
   ```
2. Check observation timestamps in SQLite:
   ```sql
   SELECT source_provider, MAX(observation_time) FROM raw_ingestion_log GROUP BY source_provider;
   ```

---

## 3. Diagnostic Checklist
* Is the background scheduler running (`systemctl status aerocast-ingest`)?
* Has the upstream IMD radar FTP/HTTP upload pipeline experienced an operational gap?
* Did an upstream clock skew report timestamps in the future or past?

---

## 4. Mitigation & Resolution
1. **Restart Ingestion Scheduler**:
   ```bash
   curl -X POST "http://localhost:8000/api/system/scheduler/restart" -H "X-API-Key: aerocast_admin_dev_token"
   ```
2. **Engage Fallback Provider**:
   Switch from primary radar feed to secondary composite radar (e.g. RainViewer API).
3. **Notify Civil Protection**:
   If staleness exceeds 30 minutes, automatically append warning to CAP bulletins: `ADVISORY: Nowcast operating on delayed atmospheric observations`.

---

## 5. Recovery Verification
* Confirm `/data/freshness` returns `overall_status: "fresh"`.
* Verify frontend globe transitions back to emerald `LIVE` badge.

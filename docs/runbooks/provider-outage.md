# Operational Runbook: Provider Outage & Ingestion Failure

## 1. Symptoms & Alert Trigger
* Circuit breaker transitions to `OPEN` for an external provider (IMD Radar, Blitzortung, INSAT-3D, or Open-Meteo).
* `/api/system/health` reports `"providers": {"state": "DEGRADED"}`.
* Logs display `circuit_breaker_opened` or `provider_timeout`.

---

## 2. Confirmation Steps
1. Query provider status:
   ```bash
   curl -s http://localhost:8000/api/system/providers | jq .
   ```
2. Check provider health in SQLite:
   ```sql
   SELECT * FROM provider_status WHERE state IN ('DEGRADED', 'OPEN');
   ```

---

## 3. Diagnostic Checklist
* Is upstream provider undergoing scheduled maintenance?
* Has upstream endpoint IP or TLS certificate changed?
* Is outbound port 443/80 blocked by network firewall?

---

## 4. Safe Mitigation & Automated Fallback
* Ingestion engine automatically engages secondary providers (e.g. RainViewer if IMD is unreachable; ECMWF if Open-Meteo is down).
* If lightning network is down, the model degrades safely to radar-dominant convective nowcasting with `data_mode = 'degraded'`.
* Operators can manually force fallback via:
  ```bash
  curl -X POST "http://localhost:8000/api/providers/fallback/trigger?source=radar&provider=rainviewer" \
       -H "X-API-Key: aerocast_operator_dev_token"
  ```

---

## 5. Recovery Verification
1. Verify circuit breaker enters `HALF_OPEN` and resets to `HEALTHY` after cooldown window.
2. Confirm `/ready` probe returns 200 OK with `overall_status: HEALTHY`.

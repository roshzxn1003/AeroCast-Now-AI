# Operational Data Infrastructure Runbook (Phase 9)

## 1. System Health Monitoring
Operators and duty meteorologists can inspect live ingestion health via the operational API:
- `GET /data/health`: Provider status, circuit breaker states, latency, and failovers.
- `GET /data/freshness`: Data age in seconds and refresh category (`FRESH`, `AGING`, `STALE`, `EXPIRED`).
- `GET /data/gate`: Pre-inference safety validation result (`READY`, `DEGRADED`, `BLOCKED`).

---

## 2. Handling Failover Scenarios

### Scenario A: IMD DWR Network Unreachable
- **System Action**: After 3 consecutive timeouts or errors, `IMD_DWR` circuit breaker trips to `OPEN`. Ingestion automatically fails over to `RAINVIEWER_RADAR`.
- **Operator Notification**: Dashboard displays alert badge: `RADAR: FAILOVER ACTIVE (RAINVIEWER_RADAR)`.
- **Recovery**: Circuit enters `HALF_OPEN` after 60s cooldown and sends a canary probe. Upon successful scan from IMD, traffic automatically shifts back to Primary (`IMD_DWR`).

### Scenario B: Cloud Cover Satellite Outage
- **System Action**: `INSAT_3D` failure trips circuit; secondary `OPEN_METEO_CLOUD` proxy provides calibrated brightness temperature grids tagged with `CanonicalQualityFlag.SUSPECT`.
- **Inference Gate Action**: Gate flags `DEGRADED` status with notification: `Domain SATELLITE operating on secondary fallback`. Forecast generation continues with warning caveats.

### Scenario C: Corrupted Data / Sensor Anomaly (Inference Block)
- **Condition**: NaN values, unphysical sensor values, or total radar absence across $\ge 3$ consecutive timesteps.
- **System Action**: `InferenceReadinessGate` transitions to `BLOCKED`. Model forward pass is prevented.
- **Resolution**: Inspect provider feed logs (`raw_ingestion_log`), verify upstream sensor telemetry, or trigger manual reset via API.

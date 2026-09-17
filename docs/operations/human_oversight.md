# Operational Human Oversight & Decision Governance Protocol

**System**: AeroCast-Now AI  
**Document ID**: DOC-OPS-002  
**Status**: MANDATORY OPERATIONAL REQUIREMENT  
**Effective Date**: September 17, 2026  
**Authority**: Head of Meteorological Operations & Civil Safety Compliance  

---

## 1. Principles of Human Oversight

AeroCast-Now AI operates strictly under an **Assistive Decision-Support Paradigm (ADSP)**. Due to the high-consequence nature of severe weather nowcasting (life safety, aviation routing, municipal emergency response) and the known physical limitations of Deep Learning models (spatial smoothing, false alarm spikes during anomalous propagation, class imbalance), **fully autonomous alert dissemination is strictly prohibited**.

No automated siren, public broadcast, or external emergency warning may be emitted without explicit, authenticated human forecaster verification and sign-off.

```
+-----------------------------------------------------------------------------+
|                      HUMAN OVERSIGHT CONTROL ARCHITECTURE                   |
+-----------------------------------------------------------------------------+
|                                                                             |
|  +--------------------+         +--------------------+                      |
|  |  Multi-Sensor      |         |  ConvLSTM2D Neural |                      |
|  |  Ingestion & QC    |         |  Nowcasting Engine |                      |
|  +---------+----------+         +---------+----------+                      |
|            |                              |                                 |
|            +--------------+---------------+                                 |
|                           |                                                 |
|                           v                                                 |
|               +-----------------------+                                     |
|               |  Rule-Based Alert     |                                     |
|               |  Synthesis Engine     |                                     |
|               +-----------+-----------+                                     |
|                           |                                                 |
|            [ Draft CAP Warning Generated ]                                  |
|                           |                                                 |
|                           v                                                 |
|               +-----------------------+                                     |
|               | OPERATIONAL DASHBOARD |                                     |
|               | (Forecaster Review)   |                                     |
|               +-----------+-----------+                                     |
|                           |                                                 |
|            +--------------+--------------+                                  |
|            |                             |                                  |
|     [ REJECT / SUPPRESS ]         [ APPROVE & SIGN ]                        |
|            |                             |                                  |
|            v                             v                                  |
|   +-------------------+         +-------------------+                       |
|   | Audit Log Reason: |         | Cryptographic     |                       |
|   | Radar Clutter /   |         | Signature + Token |                       |
|   | False Trigger     |         +---------+---------+                       |
|   +-------------------+                   |                                 |
|                                           v                                 |
|                                 +-------------------+                       |
|                                 | External Broadcast|                       |
|                                 | (IMD / NDMA / CAP)|                       |
|                                 +-------------------+                       |
+-----------------------------------------------------------------------------+
```

---

## 2. Operational Roles & Responsibilities

### 2.1 Role Matrix & Access Hierarchy

| Role Code | Operational Title | Primary Responsibilities | Authorization Scope |
|:---|:---|:---|:---|
| **FORECASTER** | Duty Meteorologist | Live radar/satellite surveillance, nowcast verification, alert validation, manual override. | Approve Level Orange alerts, suppress false alarms, draft bulletins. |
| **LEAD_MET** | Senior Lead Meteorologist | Shift supervision, severe convective event oversight, Level Red warning sign-off. | Approve Level Red (Siren) alerts, sign model promotion reviews, declare degraded modes. |
| **OPS_ADMIN** | Platform / MLOps Admin | Infrastructure health, database replication, container orchestrator, network failover. | Trigger disaster recovery failover, execute database restore, deploy verified software. |
| **VIEWER** | Public / Municipal Observer | Situational awareness, viewing verified advisories and public map displays. | Read-only access to published warnings and historical radar loops. |

---

## 3. Tiered Alert Clearance Protocols

Every alert generated by the AeroCast-Now rule engine enters one of three operational clearance workflows based on severity:

### 3.1 Advisory (Yellow — Moderate Convective Potential)
- **Criteria**: Radar reflectivity $30\text{--}40\text{ dBZ}$, lightning flash rate $5\text{--}15\text{ flashes/min}$, wind gusts $< 45\text{ km/h}$.
- **Workflow**: 
  - System logs advisory to the active dashboard.
  - Automatically routed to the forecaster queue with a passive visual notification.
  - Forecaster acknowledgment requested within 15 minutes; auto-expires if not renewed.
  - External sirens are **disabled**.

### 3.2 Warning (Orange — Severe Thunderstorm Imminent)
- **Criteria**: Radar reflectivity $40\text{--}50\text{ dBZ}$, 2-sigma lightning jump detected, cloud-top $T_B < 220\text{ K}$, wind gusts $45\text{--}70\text{ km/h}$.
- **Workflow**:
  - High-priority audible and visual alert in the forecaster console.
  - System generates a pre-formatted Common Alerting Protocol (CAP v1.2) XML draft.
  - **Mandatory HITL Action**: Forecaster must review radar VIL, lightning trend, and satellite channel.
  - Forecaster selects:
    - **[APPROVE & DISPATCH]**: Forecaster clicks approve, enters operator credential, alert is dispatched to district administration and website.
    - **[MODIFY & DISPATCH]**: Forecaster edits boundary polygon or lead time before dispatch.
    - **[DISMISS / SUPPRESS]**: Forecaster marks as non-meteorological (e.g. sea breeze clutter) and enters dismissal rationale.

### 3.3 Emergency / Siren (Red — Extreme Convective Hazard / Microburst / Severe Lightning)
- **Criteria**: Radar reflectivity $\ge 50\text{ dBZ}$, lightning jump $\ge 30\text{ flashes/min}$, mesocyclone / strong divergence, wind gusts $\ge 70\text{ km/h}$.
- **Workflow**:
  - Full-screen flashing console takeover on all active forecaster terminals.
  - Dual-key authorization required: Duty Forecaster initiates approval; Senior Lead Meteorologist (or designated secondary forecaster) provides secondary authorization.
  - Required review checklist verified before signature:
    1. Confirm multi-radar / satellite cross-correlation (exclude AP/anomalous propagation).
    2. Confirm lightning strike cluster consistency with radar core.
    3. Verify target polygon intersects inhabited urban/airfield infrastructure.
  - Dispatch triggers automated CAP alerts, district emergency siren activation, and airport ground stoppage advisory.

---

## 4. Emergency Kill Switch & False Alarm Suppression

### 4.1 Master Emergency Kill Switch
If an unvalidated siren, erroneous broadcast, or cascading false alarm loop occurs:
- **API Endpoint**: `POST /api/alerts/kill-switch`
- **CLI Command**: `PYTHONPATH=backend ./venv/bin/python -m reliability.kill_switch --revoke-all --reason "Operator manual abort"`
- **Execution Latency**: $< 1.0\text{ second}$ ($0.08\text{ ms}$ verified during Phase 13 drill).
- **System Action**:
  - Immediately broadcasts cancellation CAP message (`status: Cancel`, `msgType: Cancel`).
  - Sends immediate kill signal to hardware siren relay controllers.
  - Transitions the Alert Service into `MUTED` status.
  - Emits CRITICAL audit log entry with operator ID and client IP.

### 4.2 False Alarm Suppression Tools
Forecasters have direct UI controls to suppress specific false alarm modes:
1. **Anomalous Propagation (AP) Masking**: One-click exclusion of stationary nocturnal ground clutter echoes around coastal Chennai (Karaikal/Chennai radar false echoes).
2. **Geographical Exclusion Polygon**: Draw temporary polygon masks over military radar testing zones or RF interference sectors.
3. **Sensor Feed Muting**: If Blitzortung lightning sensor experiences burst noise due to local electrical interference, forecaster can mute lightning channel without taking radar offline.

---

## 5. Model Promotion Human Clearance

Model promotion from `CANDIDATE` to `APPROVED` production state is strictly gated by human governance. No automated pipeline script may overwrite production model weights.

### 5.1 Promotion Gating Checklist
To promote a new candidate checkpoint (`*.keras`):
- [ ] Validated on minimum 1,000 real-world historical convective sequences across 2 distinct monsoon seasons.
- [ ] Measured CSI at $\ge 35\text{ dBZ}$ exceeds active baseline.
- [ ] False Alarm Ratio ($FAR$) $\le 0.40$ on clear-air test sets.
- [ ] Numerical safety validation: 0 NaN/Inf across 10,000 synthetic test tensors.
- [ ] Warmup latency $< 2,000\text{ ms}$ on target production host.
- [ ] Signed approvals from:
  1. Lead Atmospheric Scientist (signature verifying scientific realism).
  2. Lead MLOps Engineer (signature verifying inference stability and memory bounds).

### 5.2 Promotion Procedure
```bash
PYTHONPATH=backend ./venv/bin/python scripts/promote_model.py \
  --model-id convlstm_candidate_v2 \
  --author "Dr. S. Ramanathan, Lead Met" \
  --rationale "Monsoon 2026 retrained checkpoint with focal loss" \
  --auth-token $MET_OPERATIONS_KEY
```

---

## 6. Audit Trail & Legal Traceability

Under national meteorological regulations and civil disaster liability standards, all human interactions with the warning system are logged immutably in SQLite database table `audit_log`:

```sql
CREATE TABLE audit_log (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    details_json TEXT NOT NULL
);
```

- **Logged Fields**:
  - `actor`: Username, user role, source IP, terminal ID.
  - `action`: `ALERT_APPROVED`, `ALERT_DISMISSED`, `ALERT_OVERRIDDEN`, `KILL_SWITCH_ENGAGED`, `MODEL_PROMOTED`, `MODEL_ROLLEDBACK`.
  - `details_json`: Full alert payload, pre-edit vs post-edit polygon diff, forecaster rationale notes.
- **Retention Period**: Minimum 7 years for forensic investigation of storm casualties or aviation incidents.
- **Tamper Evidence**: Weekly SHA-256 integrity hash manifests generated and backed up offsite.

---

## 7. Operational Forecaster Shift Checklist

At the beginning of each 8-hour operational shift:
1. **Verify Feed Liveness**: Confirm Doppler radar latency $< 10\text{ min}$, INSAT-3D $< 20\text{ min}$, Lightning WebSocket connected.
2. **Review System Health**: Check `/api/system/health` on dashboard (all subsystems `OK` or `HEALTHY`).
3. **Inspect Radar Calibration**: Check raw scan for clear-air AP clutter or sea-clutter lines.
4. **Test Sound & Notification Banner**: Trigger local console audio test.
5. **Review Preceding Shift Log**: Inspect any suppressed alerts or degraded mode transitions over the previous 12 hours.

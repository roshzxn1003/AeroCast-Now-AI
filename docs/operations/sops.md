# Operational Standard Operating Procedures (SOPs)

**System**: AeroCast-Now AI  
**Document ID**: DOC-OPS-001  
**Status**: APPROVED OPERATIONAL RUNBOOK  
**Total Procedures**: 18 Standard Operating Procedures  
**Date**: September 17, 2026  

---

### Standard Operating Procedure Format
Every procedure adheres to the mandatory 7-part operational lifecycle:
1. **Detection**: Monitoring metric, alert trigger, or sensory signal that reveals the incident.
2. **Diagnosis**: Step-by-step triage commands and log patterns to identify root cause.
3. **Immediate Action**: Containment steps executed within minutes to prevent blast radius expansion.
4. **Recovery**: Concrete commands to restore normal or resilient operation.
5. **Verification**: Explicit assertion criteria confirming successful operational restoration.
6. **Escalation**: Trigger criteria for calling on-call senior personnel or external providers.
7. **Documentation**: Required incident ticket entries, audit log records, and debrief actions.

---

## Index of Standard Operating Procedures
- [SOP-001: IMD Doppler Radar Feed Loss / Ingestion Timeout](#sop-001-imd-doppler-radar-feed-loss--ingestion-timeout)
- [SOP-002: INSAT-3D/3DR Satellite Data Ingestion Failure](#sop-002-insat-3d3dr-satellite-data-ingestion-failure)
- [SOP-003: Blitzortung / Lightning WebSocket Disconnection](#sop-003-blitzortung--lightning-websocket-disconnection)
- [SOP-004: Anomalous Propagation (AP) & Ground Clutter False Alarm Suppression](#sop-004-anomalous-propagation-ap--ground-clutter-false-alarm-suppression)
- [SOP-005: Model Inference Latency Degradation / Concurrency Saturation](#sop-005-model-inference-latency-degradation--concurrency-saturation)
- [SOP-006: Unphysical or Corrupted Observation Ingestion (NaN / Inf / Out-of-bounds)](#sop-006-unphysical-or-corrupted-observation-ingestion-nan--inf--out-of-bounds)
- [SOP-007: SQLite Database Lock Contention / Busy Timeout](#sop-007-sqlite-database-lock-contention--busy-timeout)
- [SOP-008: Database Corruption / WAL Journal Recovery](#sop-008-database-corruption--wal-journal-recovery)
- [SOP-009: Neural Network Checkpoint Failure / Corrupted Model Weights](#sop-009-neural-network-checkpoint-failure--corrupted-model-weights)
- [SOP-010: Emergency Siren / Public Alert Kill Switch Activation](#sop-010-emergency-siren--public-alert-kill-switch-activation)
- [SOP-011: Automated Alert Dispatch Failure / CAP Endpoint Timeout](#sop-011-automated-alert-dispatch-failure--cap-endpoint-timeout)
- [SOP-012: Extreme Convective Surge / Dual-Key Siren Clearance Procedure](#sop-012-extreme-convective-surge--dual-key-siren-clearance-procedure)
- [SOP-013: Unauthorized Administrative Access / Security Intrusion Incident](#sop-013-unauthorized-administrative-access--security-intrusion-incident)
- [SOP-014: Primary Host Hardware Outage / Disaster Recovery Failover](#sop-014-primary-host-hardware-outage--disaster-recovery-failover)
- [SOP-015: Model Drift Alert / Severe Convective Underprediction Detected](#sop-015-model-drift-alert--severe-convective-underprediction-detected)
- [SOP-016: Frontend WebGL 3D Globe Disconnection / Crash](#sop-016-frontend-webgl-3d-globe-disconnection--crash)
- [SOP-017: Network Partition / Upstream ISP Failure](#sop-017-network-partition--upstream-isp-failure)
- [SOP-018: Post-Event Severe Weather Verification & Case Study Archival](#sop-018-post-event-severe-weather-verification--case-study-archival)

---

### SOP-001: IMD Doppler Radar Feed Loss / Ingestion Timeout
1. **Detection**: Circuit breaker for `IMD_DWR` trips to `OPEN` state. Dashboard displays banner `"RADAR FEED STALE > 15 MIN"`. Health probe `/ready` reports `radar_live: false`.
2. **Diagnosis**: Run `curl -s http://localhost:8000/api/system/health | jq .components.radar`. Check ingestion daemon logs: `journalctl -u aerocast-ingestion -n 50 | grep -i "radar"`. Verify upstream IMD FTP/HTTP server reachable: `ping -c 3 dwr.imd.gov.in`.
3. **Immediate Action**: Confirm system has automatically transitioned to **Degraded Ingestion Mode** (using INSAT-3D thermal infrared and Lightning as input proxy). Ensure dashboard alerts forecaster of degraded radar availability.
4. **Recovery**: If upstream is reachable, trigger manual ingestion sync: `PYTHONPATH=backend ./venv/bin/python scripts/ingest_real_data.py --source radar --force`. Reset circuit breaker if healthy: `curl -X POST http://localhost:8000/api/system/circuit-breaker/reset?provider=IMD_DWR`.
5. **Verification**: Execute `curl http://localhost:8000/api/radar-grid?channel=dbz` and verify HTTP 200 with non-stale UTC timestamp ($< 15\text{ min}$ old).
6. **Escalation**: If radar outage exceeds 30 minutes during active monsoon operations, escalate to IMD Regional Meteorological Centre (RMC) Radar Duty Officer via hotline.
7. **Documentation**: Log downtime start, root cause (network vs radar maintenance), and recovery timestamp in Shift Log and incident ticket `INC-RADAR-<DATE>`.

---

### SOP-002: INSAT-3D/3DR Satellite Data Ingestion Failure
1. **Detection**: Satellite ingestion monitor emits alert `"INSAT3D_TIR_MISSING"`. Cloud-top temperature channel returns constant fallback values ($273.15\text{ K}$).
2. **Diagnosis**: Check MOSDAC/IMD satellite downloader: `journalctl -u aerocast-satellite -n 30`. Inspect raw download cache in `data/raw/satellite/` for truncated HDF5/NetCDF files.
3. **Immediate Action**: Flag satellite channel status as `DEGRADED` in system state. System continues nowcast using Doppler Radar and Lightning data with adjusted observational confidence weighting ($w_{rad}=0.75, w_{ltg}=0.25$).
4. **Recovery**: Remove zero-byte corrupted files: `find data/raw/satellite/ -size 0 -delete`. Re-trigger satellite ingestion task for the active orbital pass: `PYTHONPATH=backend ./venv/bin/python scripts/ingest_real_data.py --source satellite`.
5. **Verification**: Check API response: `curl http://localhost:8000/api/satellite-grid`; confirm valid brightness temperature array with min temperature $< 230\text{ K}$ over cloudy regions.
6. **Escalation**: If MOSDAC server returns HTTP 5xx or SSL handshake timeout for $> 45\text{ minutes}$, alert Systems Administrator and switch primary satellite source to backup mirror.
7. **Documentation**: Record satellite pass drop in Daily Operations Summary.

---

### SOP-003: Blitzortung / Lightning WebSocket Disconnection
1. **Detection**: Lightning flash rate drops to zero across entire domain during known active thunderstorm. Dashboard badge turns amber: `"LIGHTNING FEED DISCONNECTED"`.
2. **Diagnosis**: Inspect WebSocket daemon logs: `journalctl -u aerocast-lightning -n 40 | grep -i "websocket"`. Verify external network socket: `nc -zv live.blitzortung.org 8080`.
3. **Immediate Action**: Automated lightning jump detector switches to **Safety Hold Mode** (suppresses jump calculations; prevents false zero-baseline calculations when feed reconnects).
4. **Recovery**: Restart lightning collector service: `systemctl restart aerocast-lightning`. Ingestion engine automatically engages exponential backoff reconnection loop ($1\text{s}, 2\text{s}, 4\text{s}, \dots, 30\text{s}$).
5. **Verification**: Query `/api/lightning/recent` and confirm flashes recorded within the last 60 seconds. Verify WebSocket ping/pong latency $< 100\text{ ms}$.
6. **Escalation**: If third-party WebSocket server is down $> 20\text{ minutes}$, notify Senior Forecaster to rely on EarthNetworks/Damini backup feed.
7. **Documentation**: Record disconnection incident in Shift Operational Logbook.

---

### SOP-004: Anomalous Propagation (AP) & Ground Clutter False Alarm Suppression
1. **Detection**: Radar displays high reflectivity ($45\text{--}60\text{ dBZ}$) stationary echoes under clear-sky conditions (zero clouds on INSAT-3D, zero lightning, surface relative humidity low).
2. **Diagnosis**: Inspect Doppler radial velocity scan: radial velocity $V_r \approx 0.0\text{ m/s}$ across the echo. Check atmospheric lapse rate: nocturnal surface inversion present in radiosonde sounding.
3. **Immediate Action**: Forecaster immediately clicks **[SUPPRESS AP CLUTTER]** in the forecaster console over the affected azimuth sector (or coastal Chennai radius $0\text{--}30\text{ km}$).
4. **Recovery**: Engage Automated Clutter Filter: `curl -X POST http://localhost:8000/api/radar/filter-clutter -H "Authorization: Bearer $TOKEN" -d '{"method": "doppler_velocity_variance", "min_variance": 1.5}'`.
5. **Verification**: Verify that raw clutter echoes are removed from the nowcast input grid and draft CAP warnings for the sector are cancelled.
6. **Escalation**: If clutter persists despite filtering, notify Radar Maintenance Engineer at DWR station to calibrate STALO/COHO phase and clutter rejection notch.
7. **Documentation**: Record date, meteorological conditions (inversion strength), and azimuth affected in the AP Clutter Logbook.

---

### SOP-005: Model Inference Latency Degradation / Concurrency Saturation
1. **Detection**: Inference execution exceeds SLA limit ($> 5,000\text{ ms}$). Concurrency limiter sheds requests with HTTP 503 (`"Inference engine busy"`).
2. **Diagnosis**: Monitor host CPU and RAM utilization: `htop` or `top -b -n 1 | head -n 20`. Inspect Python process threads: `ps -eLo pid,lwp,psr,pcpu | grep $(pgrep -f api_server)`.
3. **Immediate Action**: API server automatically protects core loop by shedding excessive non-forecaster polling requests. Forecaster terminals retain guaranteed priority slot.
4. **Recovery**: If memory leak is suspected, execute graceful worker restart: `kill -HUP $(pgrep -f "uvicorn.*api_server")`. Ensure thread pool limit is set: `export OMP_NUM_THREADS=4; export TF_NUM_INTRAOP_THREADS=4`.
5. **Verification**: Run diagnostic benchmark: `PYTHONPATH=backend ./venv/bin/python scripts/run_e2e_acceptance.py`. Confirm inference latency is restored to $< 2,500\text{ ms}$.
6. **Escalation**: If high latency persists, escalate to MLOps Engineer on call.
7. **Documentation**: File performance ticket detailing CPU load, memory footprint, and concurrent connection count.

---

### SOP-006: Unphysical or Corrupted Observation Ingestion (NaN / Inf / Out-of-bounds)
1. **Detection**: Ingestion pipeline emits critical exception `"NumericalSafetyValidationError: Tensor contains NaN/Inf"`.
2. **Diagnosis**: Identify failing channel and file: `grep "NumericalSafetyValidationError" logs/aerocast.log`. Inspect raw data array bounds: check for unphysical reflectivity ($> 90\text{ dBZ}$ or $< -30\text{ dBZ}$).
3. **Immediate Action**: Ingestion gatekeeper immediately drops the corrupted time slice to prevent poisoning model state or crashing TensorFlow runtime.
4. **Recovery**: System substitutes the corrupted frame with the preceding valid time slice using linear persistence decay. Run sanitization script: `PYTHONPATH=backend ./venv/bin/python -m reliability.numerical --sanitize data/raw/`.
5. **Verification**: Run `python -c "from reliability.numerical import NumericalSafetyValidator; import numpy as np; assert NumericalSafetyValidator.validate_grid(np.load('data/cache/latest_clean_grid.npy')).is_valid"`.
6. **Escalation**: If corrupted data originates from an upstream hardware provider, contact the data provider's technical contact.
7. **Documentation**: Record file checksum and unphysical values in Data Quality Incident Log.

---

### SOP-007: SQLite Database Lock Contention / Busy Timeout
1. **Detection**: Backend logs report repeated `sqlite3.OperationalError: database is locked`. HTTP 500 errors spike on write endpoints (`/api/alerts`, `/api/observations`).
2. **Diagnosis**: Check active file locks on database: `fuser data/aerocast.sqlite3`. Check for long-running transactions or unclosed connections: `lsof data/aerocast.sqlite3`.
3. **Immediate Action**: In-flight transactions are automatically protected by `execute_with_retry` using Full Jitter exponential backoff up to 5 attempts.
4. **Recovery**: Terminate rogue stuck reader/writer process if identified: `kill -9 <STUCK_PID>`. Verify WAL journal settings: `sqlite3 data/aerocast.sqlite3 "PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;"`.
5. **Verification**: Run verification query: `PYTHONPATH=backend ./venv/bin/python -c "import sqlite3; conn = sqlite3.connect('data/aerocast.sqlite3', timeout=5.0); cur = conn.cursor(); cur.execute('SELECT count(*) FROM audit_log;'); print('Total Audit Rows:', cur.fetchone()[0]); conn.close()"`.
6. **Escalation**: If contention causes transaction aborts for $> 3\text{ minutes}$, alert Platform Administrator.
7. **Documentation**: Log lock duration and offending query in Database Operational Ticket.

---

### SOP-008: Database Corruption / WAL Journal Recovery
1. **Detection**: Backend fails to start with error `sqlite3.DatabaseError: file is not a database` or `database disk image is malformed`.
2. **Diagnosis**: Run SQLite integrity check: `sqlite3 data/aerocast.sqlite3 "PRAGMA integrity_check;"`. Check filesystem disk health: `dmesg | grep -i "I/O error"`.
3. **Immediate Action**: Stop the API service immediately to prevent further block corruption: `systemctl stop aerocast`.
4. **Recovery**: 
   - Step 1: Quarantine corrupted database: `mv data/aerocast.sqlite3 data/aerocast_corrupt_$(date +%s).sqlite3`.
   - Step 2: Restore from most recent automated backup: `cp data/backups/aerocast_daily_latest.sqlite3 data/aerocast.sqlite3`.
   - Step 3: Replay WAL delta logs if uncorrupted: `python scripts/replay_wal.py || true`.
   - Step 4: Run database migrations to ensure schema consistency: `PYTHONPATH=backend ./venv/bin/python -m db.migrations --up`.
5. **Verification**: Run `sqlite3 data/aerocast.sqlite3 "PRAGMA integrity_check;"`; confirm output is `"ok"`. Start service and verify health endpoints return HTTP 200.
6. **Escalation**: Notify Head of Infrastructure if filesystem I/O hardware errors were detected by `dmesg`.
7. **Documentation**: Complete Major Incident Report (P1) detailing recovery point objective (RPO) data loss in minutes.

---

### SOP-009: Neural Network Checkpoint Failure / Corrupted Model Weights
1. **Detection**: System startup or model reload fails with `ValueError: Unable to load model` or SHA-256 integrity mismatch. `/ready` returns HTTP 503.
2. **Diagnosis**: Check model file SHA-256 against registry: `sha256sum backend/models/convlstm_real_best.keras`. Compare with `sha256_registered` in `docs/acceptance/evidence/model_validation_evidence.json`.
3. **Immediate Action**: Warmup engine marks model subsystem as `NOT_READY`, preventing invalid inference execution.
4. **Recovery**: Execute hot rollback to the previously validated candidate checkpoint:
   ```bash
   PYTHONPATH=backend ./venv/bin/python scripts/rollback_model.py \
     --target-id convlstm_real_previous \
     --reason "Production weights file corrupted" \
     --operator "duty-ops"
   ```
5. **Verification**: Run model warmup test: `PYTHONPATH=backend ./venv/bin/python -c "from reliability.warmup import ModelWarmupEngine; from tensorflow.keras.models import load_model; m = load_model('backend/models/convlstm_real_best.keras', compile=False); res = ModelWarmupEngine.execute_warmup(m); assert res.success; print('Model Warmup OK in', res.duration_ms, 'ms')"`
6. **Escalation**: If no valid checkpoint is available locally, pull certified model weights from secure artifact store.
7. **Documentation**: Record model rollback action in `audit_log` and notify Lead MLOps Engineer.

---

### SOP-010: Emergency Siren / Public Alert Kill Switch Activation
1. **Detection**: Erroneous siren broadcast reported, false alarm storm triggered by bad data, or municipal authority requests immediate warning abort.
2. **Diagnosis**: Verify active broadcast status on dashboard. Identify Alert ID from alerting screen.
3. **Immediate Action**: **TRIGGER MASTER KILL SWITCH IMMEDIATELY**:
   - Via UI: Click the red pulsing **[EMERGENCY SIREN KILL SWITCH]** button on the top navigation bar.
   - Via API / Shell: `PYTHONPATH=backend ./venv/bin/python -m reliability.kill_switch --revoke-all --reason "Immediate operator cancellation"`
4. **Recovery**: Confirm kill switch broadcast was transmitted to hardware siren relays. Review outgoing cancellation CAP feed. Verify alert status transitions to `REVOKED`.
5. **Verification**: Check API status: `curl http://localhost:8000/api/alerts/active` returns empty array `[]`. Confirm audit log records `KILL_SWITCH_ENGAGED`.
6. **Escalation**: Phone District Disaster Control Room immediately to verbally confirm sirens have ceased sounding.
7. **Documentation**: Convene formal incident review within 2 hours. File Emergency Cancellation Report with Disaster Management Authority.

---

### SOP-011: Automated Alert Dispatch Failure / CAP Endpoint Timeout
1. **Detection**: Alert clearance succeeds locally, but NDMA / State CAP webhook returns HTTP 502/504 or network timeout.
2. **Diagnosis**: Inspect outbound dispatch queue: `journalctl -u aerocast-dispatcher -n 40`. Test external endpoint connectivity: `curl -Iv https://cap.ndma.gov.in/api/v1/inbound`.
3. **Immediate Action**: System alert queue holds failed messages in dead-letter retry ledger with exponential backoff (retrying at $10\text{s}, 30\text{s}, 60\text{s}$).
4. **Recovery**: Forecaster switches to manual secondary dissemination: export signed CAP XML directly from UI and transmit via secure meteorological telecommunications network (GTS / email / SMS).
5. **Verification**: Confirm delivery receipt from secondary channel. Monitor retry ledger until endpoint recovers.
6. **Escalation**: Alert National Emergency Communication Helpdesk if state gateway remains unreachable for $> 10\text{ minutes}$.
7. **Documentation**: Attach transmission failure log and manual delivery confirmation to shift record.

---

### SOP-012: Extreme Convective Surge / Dual-Key Siren Clearance Procedure
1. **Detection**: Severe storm cell detected with reflectivity $\ge 50\text{ dBZ}$, lightning jump $\ge 30\text{ flashes/min}$, and radial velocity convergence $\ge 25\text{ m/s}$. Dashboard triggers RED SIREN DRAFT.
2. **Diagnosis**: Duty Forecaster conducts mandatory 60-second review:
   - [x] Echo is meteorological (confirmed on INSAT-3D cloud-top IR $< 205\text{ K}$).
   - [x] Hail/Downburst signature confirmed (VIL $> 35\text{ kg/m}^2$, Echo Top $> 14\text{ km}$).
   - [x] Warning polygon covers populated municipal zones.
3. **Immediate Action**: Duty Forecaster inputs digital credentials and clicks **[REQUEST LEAD MET SIGN-OFF]**.
4. **Recovery / Clearance**: Senior Lead Meteorologist reviews the alert package on secondary console, enters master clearance passphrase, and executes dual-key dispatch:
   ```bash
   curl -X POST http://localhost:8000/api/alerts/clear-emergency \
     -H "Authorization: Bearer $LEAD_MET_TOKEN" \
     -d '{"alert_id": "ALT-20260917-01", "secondary_authorizer": "Dr. Ramanathan", "action": "CLEAR_SIREN"}'
   ```
5. **Verification**: Confirm CAP alert dispatched with `<severity>Extreme</severity>` and siren relay ACK received within $< 1,000\text{ ms}$.
6. **Escalation**: Immediately telephone State Disaster Management Authority to notify on-duty Disaster Commissioner.
7. **Documentation**: Full radar cross-section, sounding, and authorization records archived in Severe Weather Case Register.

---

### SOP-013: Unauthorized Administrative Access / Security Intrusion Incident
1. **Detection**: Security audit daemon detects failed authentication burst ($> 10\text{ attempts/min}$) or unauthorized role escalation attempt (e.g. VIEWER attempting to access `/api/system/model-registry/promote`).
2. **Diagnosis**: Inspect security audit log: `grep "AUTH_VIOLATION" logs/audit.log`. Check originating IP: `netstat -tnp | grep :8000`.
3. **Immediate Action**: Rate limiter and IP ban middleware automatically drop connections from offending IP. System revokes active session tokens for the compromised user ID.
4. **Recovery**: Rotate administrative secret keys: `export SECRET_KEY=$(openssl rand -hex 32)`. Terminate active unauthorized sessions: `systemctl restart aerocast`.
5. **Verification**: Verify that unauthorized requests receive HTTP 401/403: `curl -I http://localhost:8000/api/system/model-registry/promote` returns HTTP 401 Unauthorized.
6. **Escalation**: Escalate immediately to Chief Information Security Officer (CISO) and Computer Emergency Response Team (CERT-In).
7. **Documentation**: Export forensic log snapshot to secure offsite vault for legal analysis.

---

### SOP-014: Primary Host Hardware Outage / Disaster Recovery Failover
1. **Detection**: Primary server heartbeats cease. External load balancer reports health check failure on primary host.
2. **Diagnosis**: Check server IPMI / out-of-band console. If power supply or motherboard failure is verified:
3. **Immediate Action**: Declare site outage; initiate failover to Warm Standby Server.
4. **Recovery**:
   - Step 1: Promote Standby host to Primary: `ssh standby-node "cd /opt/aerocast && sudo ./scripts/promote_standby.sh"`.
   - Step 2: Restore latest SQLite WAL snapshot from remote replica: `sudo ./scripts/restore_db.sh --source /mnt/nfs/aerocast_latest.sqlite3`.
   - Step 3: Update DNS / VIP pointer: `dns-cli update nowcast.imd.gov.in --ip $STANDBY_IP`.
   - Step 4: Start application services: `systemctl start aerocast`.
5. **Verification**: Query standby host health endpoint: `curl -I http://$STANDBY_IP:8000/health`; verify HTTP 200 within $< 5\text{ minutes}$ from outage declaration.
6. **Escalation**: Alert hardware vendor for emergency on-site chassis repair.
7. **Documentation**: Log Total Outage Duration, RTO (Recovery Time Objective), and RPO metrics in Post-Mortem Report.

---

### SOP-015: Model Drift Alert / Severe Convective Underprediction Detected
1. **Detection**: Continuous model monitoring daemon flags weekly Threat Score ($CSI$) below baseline ($CSI < 0.05$ or $MAE > 2.5\text{ dBZ}$ across convective cells).
2. **Diagnosis**: Inspect drift report: `cat docs/operations/model_drift_report.json`. Check whether recent weather events included unseasonal synoptic patterns (e.g. winter northeast monsoon tropical depressions vs summer pre-monsoon squall lines).
3. **Immediate Action**: Transition model alert tier to **Assistive Research Only**. Increase radar heuristic weight to 80% and decrease ConvLSTM2D weight to 20% in ensemble blender.
4. **Recovery**: Trigger automated retraining pipeline with curated high-reflectivity convective samples:
   ```bash
   PYTHONPATH=backend ./venv/bin/python scripts/train_real_model.py \
     --epochs 30 \
     --focal-loss \
     --oversample-convective-cells
   ```
5. **Verification**: Evaluate retrained candidate checkpoint on validation test suite; confirm $CSI \ge 0.15$ at 35 dBZ before candidate review.
6. **Escalation**: Convene Meteorological Model Review Committee.
7. **Documentation**: Update Model Card and document retrained weights SHA-256 in Model Governance Registry.

---

### SOP-016: Frontend WebGL 3D Globe Disconnection / Crash
1. **Detection**: Forecaster console freezes or browser displays `"WebGL Context Lost"` error.
2. **Diagnosis**: Check browser console logs (`F12 -> Console`). Check GPU driver / WebGL memory allocation. Verify backend WebSocket server is emitting data: `curl -i http://localhost:8000/api/system/health`.
3. **Immediate Action**: Forecaster clicks **[2D FALLBACK MAP]** button in top toolbar to instantly switch from Three.js 3D globe to Leaflet 2D canvas without losing radar overlays.
4. **Recovery**: If browser tab is unresponsive, refresh page (`Ctrl + Shift + R`). If WebGL crashed due to hardware acceleration bug, restart browser with software rendering fallback flag.
5. **Verification**: Confirm real-time radar layer renders smoothly with current time slider.
6. **Escalation**: If issue affects multiple terminals, notify Frontend Engineering Team.
7. **Documentation**: Note workstation hardware, OS version, and browser version in Frontend Bug Tracker.

---

### SOP-017: Network Partition / Upstream ISP Failure
1. **Detection**: Multiple external providers fail simultaneously (IMD, MOSDAC, Blitzortung). Outbound alert webhooks fail.
2. **Diagnosis**: Check default gateway and external routing: `ping -c 3 8.8.8.8`. Check dual-WAN router status.
3. **Immediate Action**: Router automatically fails over to secondary leased line / 4G emergency backup cellular link.
4. **Recovery**: If automated router failover fails, manually switch network interface: `sudo ip route replace default via 192.168.2.1 dev eth1`.
5. **Verification**: Run diagnostic network check: `curl -I https://www.google.com` and `curl -I https://dwr.imd.gov.in`.
6. **Escalation**: Contact primary ISP Network Operations Center (NOC) to log leased line break.
7. **Documentation**: Record ISP ticket number and outage timeline in Operational Communications Log.

---

### SOP-018: Post-Event Severe Weather Verification & Case Study Archival
1. **Detection**: Severe weather event concludes (convective storm dissipates or moves out of radar range).
2. **Diagnosis**: Identify event time window ($t_{start}$ to $t_{end}$) and affected district polygons.
3. **Immediate Action**: Run automated case study export tool to freeze and archive all raw observations, model forecast grids, alert logs, and ground truth data:
   ```bash
   PYTHONPATH=backend ./venv/bin/python scripts/archive_case_study.py \
     --event-name "Severe_Squall_Chennai_20260917" \
     --start "2026-09-17T10:00:00Z" \
     --end "2026-09-17T18:00:00Z" \
     --output "docs/validation/cases/"
   ```
4. **Recovery / Verification**: Verify that archive package contains:
   - Raw NetCDF/HDF5 radar scans
   - ConvLSTM2D predicted reflectivity grids
   - Blitzortung lightning strike points
   - Surface AWS rain gauge readings
   - Full audit log of forecaster actions
5. **Verification**: Compute standardized verification metrics for the event: POD, FAR, CSI, ETS, and displacement errors.
6. **Escalation**: If event caused severe damage or loss of life, submit formal Scientific Verification Report to IMD Director General within 48 hours.
7. **Documentation**: Publish completed case study in `docs/validation/storm_event_case_studies.md` and upload dataset bundle to research repository.

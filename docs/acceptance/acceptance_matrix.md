# AeroCast-Now AI: Formal Operational Acceptance Matrix (Phase 13)

**Generated**: 2026-09-17  
**Status**: Completed  
**Software Version**: `v2.1.0`  
**Active Production Model**: `convlstm_real_best.keras` (v1.0.0, ResAtt-ConvLSTM2D, 191,524 parameters)  
**Overall Acceptance Decision**: **CONDITIONAL GO**  
**Operating Boundary**: **Authorized exclusively for Human-in-the-Loop Assistive Mode & Meteorological Research. Automated public siren triggering is strictly prohibited.**

---

## 1. Domain 1: Software Readiness

| Criterion ID | Requirement | Status | Evidence Summary | Evidence Location | Test Date | Env | Owner / Reviewer | Known Limitation | Residual Risk & Remediation |
| :--- | :--- | :---: | :--- | :--- | :---: | :---: | :--- | :--- | :--- |
| **SOFT-001** | FastAPI REST & Telemetry endpoints initialize without error and serve requests | **PASS** | `/health`, `/live`, `/ready`, `/api/system/health`, and `/api/radar-grid` return HTTP 200 | [`docs/acceptance/evidence/software_readiness_evidence.json`](file:///home/arun-roshan-gj/SIH/docs/acceptance/evidence/software_readiness_evidence.json) | 2026-09-17 | Testing | Backend Lead / Ops Lead | Single worker ASGI in dev environment | **Low**. Deploy with Uvicorn worker pool for multi-core scaling. |
| **SOFT-002** | React/Vite 3D Globe renders multi-layer nowcast visualizations | **PASS** | Production bundle compiled (2.9 MB); WebGL canvas renders districts, convective heatmaps, and lightning | [`docs/acceptance/evidence/e2e_acceptance_evidence.json`](file:///home/arun-roshan-gj/SIH/docs/acceptance/evidence/e2e_acceptance_evidence.json) | 2026-09-17 | Testing | Frontend Lead / UI Meteorologist | Requires WebGL2 hardware support | **Low**. 2D Leaflet fallback available for legacy clients. |
| **SOFT-003** | Zero hardcoded secrets; structured logging with secret masking | **PASS** | Git repository scan confirmed zero committed keys/tokens; StructuredJSONFormatter redacts secrets | [`docs/acceptance/evidence/security_audit_evidence.json`](file:///home/arun-roshan-gj/SIH/docs/acceptance/evidence/security_audit_evidence.json) | 2026-09-17 | Testing | Security Eng / Lead Architect | Local .env test files are gitignored | **Low**. Enforce pre-commit scanning hooks across dev team. |
| **SOFT-004** | Automated regression test coverage across all architectural subsystems | **PASS** | 64 of 64 tests pass across Phases 9, 10, 11, and 12 in 50.86s | [`docs/acceptance/evidence/software_readiness_evidence.json`](file:///home/arun-roshan-gj/SIH/docs/acceptance/evidence/software_readiness_evidence.json) | 2026-09-17 | Testing | QA Lead / Release Mgr | In-memory SQLite tests run fast | **Low**. Schedule nightly multi-hour soak testing on staging server. |

---

## 2. Domain 2: Data Readiness

| Criterion ID | Requirement | Status | Evidence Summary | Evidence Location | Test Date | Env | Owner / Reviewer | Known Limitation | Residual Risk & Remediation |
| :--- | :--- | :---: | :--- | :--- | :---: | :---: | :--- | :--- | :--- |
| **DATA-001** | Multi-cadence operational ingestion for Radar, Satellite, Lightning, and NWP | **PASS** | Adapters verified for IMD (10m), INSAT-3D (15m), Blitzortung (streaming), Open-Meteo (1h) | [`docs/acceptance/evidence/data_readiness_evidence.json`](file:///home/arun-roshan-gj/SIH/docs/acceptance/evidence/data_readiness_evidence.json) | 2026-09-17 | Testing | Data Eng / Met Consultant | Upstream IMD APIs experience outages during severe storms | **Medium**. Establish redundant dedicated IMD FTP mirror feed. |
| **DATA-002** | Strict isolation prohibiting synthetic data from masquerading as real in production | **PASS** | `DeploymentConfig.validate()` triggers Fail-Fast startup termination if `DATA_MODE=simulation` in production | [`docs/acceptance/evidence/data_readiness_evidence.json`](file:///home/arun-roshan-gj/SIH/docs/acceptance/evidence/data_readiness_evidence.json) | 2026-09-17 | Testing | Backend Lead / Security Lead | Hybrid mode allows dev fallback | **Low**. None required; verified enforced. |
| **DATA-003** | Atmospheric quality control enforces physical boundaries, bounding box, and freshness | **PASS** | `AtmosphericQualityControl` verifies dBZ bounds (-10 to 75), India domain bbox, and freshness; flags NaN | [`docs/acceptance/evidence/e2e_acceptance_evidence.json`](file:///home/arun-roshan-gj/SIH/docs/acceptance/evidence/e2e_acceptance_evidence.json) | 2026-09-17 | Testing | Data Quality / Forecaster | Ground clutter near urban Chennai | **Medium**. Implement dual-polarization correlation coefficient filters. |

---

## 3. Domain 3: ML / Model Readiness

| Criterion ID | Requirement | Status | Evidence Summary | Evidence Location | Test Date | Env | Owner / Reviewer | Known Limitation | Residual Risk & Remediation |
| :--- | :--- | :---: | :--- | :--- | :---: | :---: | :--- | :--- | :--- |
| **ML-001** | Model artifact registered with cryptographic checksum, metadata, and architecture | **PASS** | `convlstm_real_best.keras` registered with SHA-256 (`6194f04a...`) and 191,524 parameters | [`docs/acceptance/evidence/model_validation_evidence.json`](file:///home/arun-roshan-gj/SIH/docs/acceptance/evidence/model_validation_evidence.json) | 2026-09-17 | Testing | ML Eng / Data Scientist | Eager Keras execution on CPU | **Low**. Export ONNX / TensorRT runtime for edge inference. |
| **ML-002** | Model warmup engine and numerical safety prevent boot panics and invalid tensor outputs | **PASS** | `ModelWarmupEngine` passes benchmark fixture (59 ms); `NumericalSafetyValidator` aborts on NaNs | [`docs/acceptance/evidence/operational_drills_evidence.json`](file:///home/arun-roshan-gj/SIH/docs/acceptance/evidence/operational_drills_evidence.json) | 2026-09-17 | Testing | MLOps Lead / Platform Eng | Warmup adds ~900 ms to boot time | **Low**. Accepted trade-off for zero-crash stability. |

---

## 4. Domain 4: Scientific Validation

| Criterion ID | Requirement | Status | Evidence Summary | Evidence Location | Test Date | Env | Owner / Reviewer | Known Limitation | Residual Risk & Remediation |
| :--- | :--- | :---: | :--- | :--- | :---: | :---: | :--- | :--- | :--- |
| **SCI-001** | Rigorous separation of synthetic development metrics from real-world historical validation | **PASS** | Synthetic benchmarks (128 samples, CSI ~0.84) are strictly segregated from real historical validation (2,648 samples) | [`docs/acceptance/evidence/model_validation_evidence.json`](file:///home/arun-roshan-gj/SIH/docs/acceptance/evidence/model_validation_evidence.json) | 2026-09-17 | Testing | Meteorologist / Science Lead | Historical dataset size (464 training samples) remains small | **High**. Expand training dataset with 3 full convective seasons. |
| **SCI-002** | Demonstrated forecast skill at operational convective thresholds (25, 35, 45 dBZ) on real data | **FAIL** | On unseen real test data, model achieves CSI=0.0 and POD=0.0 at 35 dBZ due to class imbalance | [`docs/acceptance/evidence/model_validation_evidence.json`](file:///home/arun-roshan-gj/SIH/docs/acceptance/evidence/model_validation_evidence.json) | 2026-09-17 | Testing | Lead Data Scientist / External Met | Rare convective cores (< 1.5%) caused network to underpredict peaks | **Critical (Blocks Public Alerting)**. Retrain with convective oversampling & focal loss. |
| **SCI-003** | Baseline comparison against Persistence, Climatology, and Simple Extrapolation | **PARTIAL** | Model achieves lower MAE (0.467 dBZ) than persistence (0.512 dBZ), but persistence outperforms model on +15m convective CSI (0.021 vs 0.000) | [`docs/acceptance/evidence/baseline_comparison_evidence.json`](file:///home/arun-roshan-gj/SIH/docs/acceptance/evidence/baseline_comparison_evidence.json) | 2026-09-17 | Testing | Met Analyst / Lead Data Scientist | Neural network smooths out convective peaks | **High**. Implement optical flow advection blending for 0–30 min nowcasts. |
| **SCI-004** | Total lightning nowcast & 2-sigma jump precursor validation | **PASS** | 2-sigma jump algorithm detects rapid updraft electrification ($DFR/dt > 2\sigma$) | [`docs/validation/lightning_validation.md`](file:///home/arun-roshan-gj/SIH/docs/validation/lightning_validation.md) | 2026-09-17 | Testing | Lightning Spec / Ops Lead | Jump precursor has high false alarm rate in non-severe storms | **Medium**. Gate jump alerts on co-located radar VIL $> 20\text{ kg/m}^2$. |
| **SCI-005** | Probabilistic uncertainty quantification and calibration | **NOT EVALUATED** | Model is deterministic; probabilistic calibration (Brier score, reliability diagrams) is not currently available | [`docs/validation/uncertainty_and_calibration.md`](file:///home/arun-roshan-gj/SIH/docs/validation/uncertainty_and_calibration.md) | 2026-09-17 | Testing | Science Lead / Lead Architect | No probabilistic ensemble output | **Medium**. Design Monte Carlo Dropout / Deep Ensemble in Phase 14. |

---

## 5. Domain 5: Operational Readiness

| Criterion ID | Requirement | Status | Evidence Summary | Evidence Location | Test Date | Env | Owner / Reviewer | Known Limitation | Residual Risk & Remediation |
| :--- | :--- | :---: | :--- | :--- | :---: | :---: | :--- | :--- | :--- |
| **OPER-001** | Transparent state machine transitions (`HEALTHY`, `DEGRADED`, `STALE`, `NOT_READY`, `FAILED`) | **PASS** | Verified across failure drills DRILL-001 to DRILL-008; circuit breakers trip cleanly, UI communicates data state | [`docs/acceptance/evidence/operational_drills_evidence.json`](file:///home/arun-roshan-gj/SIH/docs/acceptance/evidence/operational_drills_evidence.json) | 2026-09-17 | Testing | SRE Lead / Ops Lead | Degraded mode uses lower resolution satellite proxy | **Low**. Train operators to recognize degraded satellite mode. |
| **OPER-002** | Concurrency bounds prevent thread starvation and memory exhaustion under burst loads | **PASS** | `InferenceConcurrencyLimiter` caps concurrent inferences to 2; excess traffic queues or receives HTTP 503 | [`docs/acceptance/evidence/operational_drills_evidence.json`](file:///home/arun-roshan-gj/SIH/docs/acceptance/evidence/operational_drills_evidence.json) | 2026-09-17 | Testing | Backend Lead / SRE Lead | Bursts $> 16\text{ req/s}$ receive 503 | **Low**. Autoscaling backend containers handles traffic surges. |
| **OPER-003** | 18 Standard Operating Procedures (SOPs) documented with detection, action, and recovery | **PASS** | Complete operational manual covering provider failures, DB corruption, model rollback, and promotions | [`docs/operations/sops.md`](file:///home/arun-roshan-gj/SIH/docs/operations/sops.md) | 2026-09-17 | Testing | Ops Lead / SRE Lead | Operator training required | **Low**. Conduct bi-weekly operator tabletop walkthroughs. |

---

## 6. Domain 6: Security Readiness

| Criterion ID | Requirement | Status | Evidence Summary | Evidence Location | Test Date | Env | Owner / Reviewer | Known Limitation | Residual Risk & Remediation |
| :--- | :--- | :---: | :--- | :--- | :---: | :---: | :--- | :--- | :--- |
| **SEC-001** | OWASP security headers enforced; payload size strictly limited (HTTP 413) | **PASS** | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection` verified; 10 MB payload ceiling | [`docs/acceptance/evidence/security_audit_evidence.json`](file:///home/arun-roshan-gj/SIH/docs/acceptance/evidence/security_audit_evidence.json) | 2026-09-17 | Testing | Security Eng / Backend Lead | HSTS omitted in dev | **Low**. HSTS active in production reverse proxy. |
| **SEC-002** | Role-Based Access Control (RBAC) protects administrative endpoints | **PASS** | Unauthorized POST to `/api/system/model-registry/promote` rejected with HTTP 403 Forbidden | [`docs/acceptance/evidence/security_audit_evidence.json`](file:///home/arun-roshan-gj/SIH/docs/acceptance/evidence/security_audit_evidence.json) | 2026-09-17 | Testing | Security Eng / Platform Eng | Current implementation uses API tokens | **Low**. Integrate OAuth2 / Keycloak OIDC for multi-agency logins. |

---

## 7. Domain 7: Disaster Recovery Readiness

| Criterion ID | Requirement | Status | Evidence Summary | Evidence Location | Test Date | Env | Owner / Reviewer | Known Limitation | Residual Risk & Remediation |
| :--- | :--- | :---: | :--- | :--- | :---: | :---: | :--- | :--- | :--- |
| **DR-001** | Online SQLite WAL snapshot backup and automated restoration drill with verified parity | **PASS** | Automated drill achieved measured RTO of 28.5 ms (target $< 15$ min), RPO $< 1$ hour, 100% table row parity across 7 tables | [`reports/disaster_recovery_test.json`](file:///home/arun-roshan-gj/SIH/reports/disaster_recovery_test.json) | 2026-09-16 | Testing | DBA / SRE Lead | Backups stored locally on host NVMe | **Medium**. Configure daily rsync / AWS S3 bucket sync for off-site disaster recovery. |

---

## 8. Domain 8: Governance Readiness

| Criterion ID | Requirement | Status | Evidence Summary | Evidence Location | Test Date | Env | Owner / Reviewer | Known Limitation | Residual Risk & Remediation |
| :--- | :--- | :---: | :--- | :--- | :---: | :---: | :--- | :--- | :--- |
| **GOV-001** | Mandatory Human-in-the-Loop oversight for high-impact warnings and model promotion | **PASS** | Documented in `human_oversight.md`; automated siren broadcast prohibited; dual-operator promotion sign-off required | [`docs/operations/human_oversight.md`](file:///home/arun-roshan-gj/SIH/docs/operations/human_oversight.md) | 2026-09-17 | Testing | Lead Met / Disaster Liaison | Requires 24/7 forecaster staffing | **Low**. Maintain duty roster during active pre-monsoon and northeast monsoon seasons. |
| **GOV-002** | Alert governance lifecycle, CAP v1.2 schema compliance, and deduplication suppression | **PASS** | Full alert lifecycle implemented with 20-min deduplication window and multi-sector impact protocols | [`docs/governance/alert_governance.md`](file:///home/arun-roshan-gj/SIH/docs/governance/alert_governance.md) | 2026-09-17 | Testing | Disaster Liaison / Lead Met | CAP XML broadcast requires NDMA integration | **Low**. Complete NDMA SACHET gateway protocol integration. |

---

## 9. Summary Statistics & Acceptance Conclusion

| Domain | Total Evaluated | PASS | PARTIAL | FAIL | NOT EVALUATED | Domain Readiness |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Software Readiness** | 4 | 4 | 0 | 0 | 0 | **PASS** (100%) |
| **Data Readiness** | 3 | 3 | 0 | 0 | 0 | **PASS** (100%) |
| **ML / Model Readiness** | 2 | 2 | 0 | 0 | 0 | **PASS** (100%) |
| **Scientific Validation** | 5 | 2 | 1 | 1 | 1 | **CONDITIONAL / PARTIAL** (Convective Hit Skill Pending) |
| **Operational Readiness**| 3 | 3 | 0 | 0 | 0 | **PASS** (100%) |
| **Security Readiness** | 2 | 2 | 0 | 0 | 0 | **PASS** (100%) |
| **Disaster Recovery** | 1 | 1 | 0 | 0 | 0 | **PASS** (100%) |
| **Governance Readiness** | 2 | 2 | 0 | 0 | 0 | **PASS** (100%) |
| **TOTAL** | **22** | **19** | **1** | **1** | **1** | **CONDITIONAL GO** |

> [!IMPORTANT]
> **Operational Boundary Mandate**:
> Because Criterion **SCI-002** (`CSI=0.0` at $35\text{ dBZ}$ on real-world historical data) fails the threshold for autonomous warning issuance, AeroCast-Now AI is formally certified as **CONDITIONAL GO**. It is strictly restricted to **Human-in-the-Loop Assistive Mode** where certified operational forecasters review all nowcasts. Fully automated sirens or public CAP broadcasts are prohibited until retrained with a large, balanced convective dataset.

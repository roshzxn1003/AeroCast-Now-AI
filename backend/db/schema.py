"""
Relational Schema Definition for AeroCast-Now AI SQLite Store.
Phase 8 Production Operations & Verification.
"""

SCHEMA_SQL = """
-- =============================================================================
-- 1. Atmospheric Observations (Raw & Normalized Preservation)
-- =============================================================================
CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    obs_id TEXT UNIQUE NOT NULL,
    source TEXT NOT NULL,
    dataset TEXT NOT NULL,
    observation_time TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    latitude REAL,
    longitude REAL,
    coverage_bbox TEXT,
    variable TEXT NOT NULL,
    unit TEXT NOT NULL,
    value_numeric REAL,
    payload_json TEXT,
    quality_status TEXT NOT NULL CHECK (quality_status IN ('VALID', 'SUSPECT', 'MISSING', 'STALE', 'INVALID')),
    quality_reason TEXT,
    processing_version TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_obs_time_source ON observations (observation_time, source);
CREATE INDEX IF NOT EXISTS idx_obs_variable ON observations (variable);
CREATE INDEX IF NOT EXISTS idx_obs_quality ON observations (quality_status);

-- =============================================================================
-- 2. Forecast Predictions (Immutable Forecast Ledger)
-- =============================================================================
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id TEXT UNIQUE NOT NULL,
    model_id TEXT NOT NULL,
    model_version TEXT NOT NULL,
    model_hash TEXT NOT NULL,
    station TEXT,
    generated_at TEXT NOT NULL,
    valid_time TEXT NOT NULL,
    lead_time_min INTEGER NOT NULL,
    max_dbz REAL,
    max_vil REAL,
    has_jump INTEGER DEFAULT 0,
    storm_count INTEGER DEFAULT 0,
    input_timestamps_json TEXT,
    data_sources_json TEXT,
    prediction_payload_json TEXT,
    verified INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_pred_valid_time ON predictions (valid_time);
CREATE INDEX IF NOT EXISTS idx_pred_station_lead ON predictions (station, lead_time_min);
CREATE INDEX IF NOT EXISTS idx_pred_verified ON predictions (verified);

-- =============================================================================
-- 3. Automated Forecast Verifications (Prediction vs. Observed Truth)
-- =============================================================================
CREATE TABLE IF NOT EXISTS verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    verification_id TEXT UNIQUE NOT NULL,
    prediction_id TEXT NOT NULL REFERENCES predictions(prediction_id),
    verified_at TEXT NOT NULL,
    lead_time_min INTEGER NOT NULL,
    observed_max_dbz REAL,
    predicted_max_dbz REAL,
    dbz_error REAL,
    hit INTEGER DEFAULT 0,
    miss INTEGER DEFAULT 0,
    false_alarm INTEGER DEFAULT 0,
    correct_negative INTEGER DEFAULT 0,
    location_error_km REAL,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_verif_pred ON verifications (prediction_id);
CREATE INDEX IF NOT EXISTS idx_verif_lead ON verifications (lead_time_min);

-- =============================================================================
-- 4. Severe Convective Alerts (CAP v1.2 Compliant)
-- =============================================================================
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id TEXT UNIQUE NOT NULL,
    event_id TEXT,
    severity TEXT NOT NULL,
    urgency TEXT NOT NULL,
    certainty TEXT NOT NULL,
    headline TEXT NOT NULL,
    description TEXT NOT NULL,
    instruction TEXT,
    area_desc TEXT,
    created_at TEXT NOT NULL,
    effective_time TEXT NOT NULL,
    expires_time TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('NEW', 'ACKNOWLEDGED', 'ACTIVE', 'UPDATED', 'EXPIRED', 'CLOSED')),
    acknowledged_at TEXT,
    acknowledged_by TEXT,
    source TEXT NOT NULL,
    model_version TEXT NOT NULL,
    risk_score REAL,
    risk_basis_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts (status);
CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts (created_at);

-- =============================================================================
-- 5. Model Registry (Lifecycle, Promotion & Rollback)
-- =============================================================================
CREATE TABLE IF NOT EXISTS model_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id TEXT UNIQUE NOT NULL,
    model_name TEXT NOT NULL,
    version TEXT NOT NULL,
    stage TEXT NOT NULL CHECK (stage IN ('EXPERIMENTAL', 'CANDIDATE', 'VALIDATED', 'STAGING', 'PRODUCTION', 'RETIRED', 'REJECTED', 'TRAINING', 'VALIDATION')),
    architecture TEXT NOT NULL,
    dataset_version TEXT NOT NULL,
    feature_version TEXT NOT NULL,
    weights_path TEXT NOT NULL,
    model_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    promoted_at TEXT,
    promoted_by TEXT,
    metrics_json TEXT,
    limitations_json TEXT,
    is_active_production INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_model_stage ON model_registry (stage);
CREATE INDEX IF NOT EXISTS idx_model_prod ON model_registry (is_active_production);

-- =============================================================================
-- 6. Operational Audit Log
-- =============================================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    details_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_log (timestamp);

-- =============================================================================
-- 7. Raw Ingestion Log (Phase 9 - Raw Data Preservation & Deduplication)
-- =============================================================================
CREATE TABLE IF NOT EXISTS raw_ingestion_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ingestion_id TEXT UNIQUE NOT NULL,
    source_provider TEXT NOT NULL,
    dataset TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    file_size_bytes INTEGER,
    ingested_at TEXT NOT NULL,
    observation_time TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('STORED', 'PROCESSED', 'FAILED', 'DUPLICATE')),
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_raw_hash ON raw_ingestion_log (file_hash);
CREATE INDEX IF NOT EXISTS idx_raw_provider_time ON raw_ingestion_log (source_provider, observation_time);

-- =============================================================================
-- 8. Live Provider Status & Health (Phase 9 - Multi-Source Monitoring)
-- =============================================================================
CREATE TABLE IF NOT EXISTS provider_status (
    provider_id TEXT UNIQUE NOT NULL PRIMARY KEY,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('HEALTHY', 'DEGRADED', 'OPEN', 'HALF_OPEN')),
    consecutive_failures INTEGER DEFAULT 0,
    total_requests INTEGER DEFAULT 0,
    total_failures INTEGER DEFAULT 0,
    last_success_time TEXT,
    last_failure_time TEXT,
    last_latency_ms REAL,
    fallback_count INTEGER DEFAULT 0,
    updated_at TEXT NOT NULL
);

-- =============================================================================
-- 9. Fallback & Failover Event Ledger (Phase 9 - Redundancy Auditability)
-- =============================================================================
CREATE TABLE IF NOT EXISTS fallback_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE NOT NULL,
    source_type TEXT NOT NULL,
    primary_provider TEXT NOT NULL,
    secondary_provider TEXT NOT NULL,
    fallback_reason TEXT,
    timestamp TEXT NOT NULL,
    restored_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_fallback_time ON fallback_events (timestamp);
CREATE INDEX IF NOT EXISTS idx_fallback_type ON fallback_events (source_type);

-- =============================================================================
-- 10. Atmospheric Data Quality Log (Phase 9 - Real-time QC Tracking)
-- =============================================================================
CREATE TABLE IF NOT EXISTS data_quality_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    obs_id TEXT NOT NULL,
    source_provider TEXT NOT NULL,
    variable TEXT NOT NULL,
    qc_flag TEXT NOT NULL,
    qc_rule TEXT NOT NULL,
    observed_value REAL,
    expected_range TEXT,
    timestamp TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_qc_obs_time ON data_quality_log (timestamp, variable);
CREATE INDEX IF NOT EXISTS idx_qc_flag ON data_quality_log (qc_flag);

-- =============================================================================
-- 11. Model Artifact Integrity Ledger (Phase 10 - Checksum & Artifact Security)
-- =============================================================================
CREATE TABLE IF NOT EXISTS model_artifacts (
    artifact_id TEXT UNIQUE NOT NULL PRIMARY KEY,
    model_id TEXT NOT NULL,
    version TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    file_size_bytes INTEGER,
    framework_version TEXT,
    python_version TEXT,
    created_at TEXT NOT NULL,
    verified_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('VALID', 'CORRUPT', 'MISSING'))
);

CREATE INDEX IF NOT EXISTS idx_art_model ON model_artifacts (model_id, version);
CREATE INDEX IF NOT EXISTS idx_art_hash ON model_artifacts (file_hash);

-- =============================================================================
-- 12. Multi-Horizon Forecast Verifications (Phase 10 - +15m to +120m Decomposition)
-- =============================================================================
CREATE TABLE IF NOT EXISTS multi_horizon_verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    verification_id TEXT UNIQUE NOT NULL,
    prediction_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    model_version TEXT NOT NULL,
    horizon_min INTEGER NOT NULL,
    initialization_time TEXT NOT NULL,
    valid_time TEXT NOT NULL,
    verified_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('VERIFIED', 'UNAVAILABLE', 'FAILED', 'PENDING')),
    mae REAL,
    rmse REAL,
    bias REAL,
    correlation REAL,
    threshold_dbz REAL DEFAULT 35.0,
    pod REAL,
    far REAL,
    csi REAL,
    hss REAL,
    ets REAL,
    f1 REAL,
    persistence_mae REAL,
    persistence_csi REAL,
    climatology_mae REAL,
    skill_score_vs_persistence REAL,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_mh_pred ON multi_horizon_verifications (prediction_id);
CREATE INDEX IF NOT EXISTS idx_mh_model_horizon ON multi_horizon_verifications (model_id, horizon_min);
CREATE INDEX IF NOT EXISTS idx_mh_status ON multi_horizon_verifications (status);

-- =============================================================================
-- 13. Convective Storm Events & Case Studies (Phase 10 - Event-Based Verification)
-- =============================================================================
CREATE TABLE IF NOT EXISTS storm_events (
    event_id TEXT UNIQUE NOT NULL PRIMARY KEY,
    name TEXT,
    region TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT,
    severity TEXT NOT NULL,
    max_observed_dbz REAL,
    max_predicted_dbz REAL,
    first_model_detection_time TEXT,
    first_observation_time TEXT,
    detection_lead_time_min REAL,
    location_error_km REAL,
    classification TEXT CHECK (classification IN ('DETECTED', 'MISSED', 'FALSE_ALARM')),
    false_alarm_cause TEXT,
    miss_contributing_factors TEXT,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_storm_event_time ON storm_events (start_time);
CREATE INDEX IF NOT EXISTS idx_storm_event_class ON storm_events (classification);

-- =============================================================================
-- 14. Data & Performance Drift Metrics (Phase 10 - PSI & KS Tests)
-- =============================================================================
CREATE TABLE IF NOT EXISTS drift_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evaluation_time TEXT NOT NULL,
    variable TEXT NOT NULL,
    metric_type TEXT NOT NULL,
    metric_value REAL NOT NULL,
    p_value REAL,
    drift_status TEXT NOT NULL CHECK (drift_status IN ('STABLE', 'WARNING', 'DRIFT_DETECTED')),
    baseline_period TEXT,
    current_period TEXT,
    details_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_drift_time_var ON drift_metrics (evaluation_time, variable);
CREATE INDEX IF NOT EXISTS idx_drift_status ON drift_metrics (drift_status);

-- =============================================================================
-- 15. Controlled Retraining Requests (Phase 10 - Human-In-The-Loop ML)
-- =============================================================================
CREATE TABLE IF NOT EXISTS retraining_requests (
    request_id TEXT UNIQUE NOT NULL PRIMARY KEY,
    model_id TEXT NOT NULL,
    current_version TEXT NOT NULL,
    trigger_type TEXT NOT NULL CHECK (trigger_type IN ('SCHEDULED', 'DATA_DRIFT', 'PERFORMANCE_DEGRADATION', 'NEW_DATASET', 'MANUAL')),
    trigger_reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PENDING', 'APPROVED', 'IN_PROGRESS', 'EVALUATED', 'REJECTED', 'PROMOTED')),
    reviewed_by TEXT,
    reviewed_at TEXT,
    candidate_model_id TEXT,
    offline_eval_summary_json TEXT,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_retrain_status ON retraining_requests (status);
CREATE INDEX IF NOT EXISTS idx_retrain_model ON retraining_requests (model_id);

-- =============================================================================
-- 16. Research & Holdout Experiments (Phase 10 - Reproducible Evaluation)
-- =============================================================================
CREATE TABLE IF NOT EXISTS experiments (
    experiment_id TEXT UNIQUE NOT NULL PRIMARY KEY,
    name TEXT NOT NULL,
    model_id TEXT NOT NULL,
    model_version TEXT NOT NULL,
    dataset_version TEXT NOT NULL,
    feature_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    training_period TEXT,
    holdout_test_period TEXT,
    hyperparameters_json TEXT,
    metrics_json TEXT,
    holdout_metrics_json TEXT,
    status TEXT NOT NULL,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_exp_model ON experiments (model_id, model_version);

-- =============================================================================
-- 17. Model Lifecycle Audit Actions (Phase 10 - Comprehensive Traceability)
-- =============================================================================
CREATE TABLE IF NOT EXISTS model_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_id TEXT UNIQUE NOT NULL,
    timestamp TEXT NOT NULL,
    action_type TEXT NOT NULL CHECK (action_type IN ('TRAIN', 'EVALUATE', 'REGISTER', 'STAGE', 'PROMOTE', 'ROLLBACK', 'RETIRE', 'REJECT')),
    model_id TEXT NOT NULL,
    version TEXT NOT NULL,
    actor TEXT NOT NULL,
    reason TEXT NOT NULL,
    previous_state TEXT,
    new_state TEXT,
    details_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_action_model ON model_actions (model_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_action_type ON model_actions (action_type);
"""



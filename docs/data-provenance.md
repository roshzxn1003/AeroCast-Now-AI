# Data Provenance, Audit Trails & Cryptographic Integrity (Phase 9)

## 1. Cryptographic Lineage & Deduplication
Every incoming observation payload, normalized canonical frame, and resulting nowcast maintains an unbroken cryptographic lineage.

### SHA-256 Payload Hash
Incoming raw payloads are hashed immediately upon network arrival:
$$\text{Hash} = \text{SHA-256}(\text{Raw Payload Bytes})$$
This hash serves two purposes:
1. **Deduplication**: Queried against `raw_ingestion_log.file_hash`. If already stored, disk write and re-parsing are bypassed (`status = DUPLICATE`).
2. **Tamper Evidence**: Validates that raw files on disk have not undergone offline alteration.

### Canonical Observation Checksum
Canonical observations hash core metadata and array content:
$$\text{Checksum} = \text{SHA-256}(\text{source} \parallel \text{dataset} \parallel \text{variable} \parallel \text{timestamp} \parallel \text{grid\_data\_bytes})$$

---

## 2. Relational Audit Schema
The SQLite WAL store maintains dedicated audit tables:
- `raw_ingestion_log`: Full provenance of every ingested file, provider, timestamp, size, and hash.
- `provider_status`: Live telemetry, failure counters, and latency history per provider.
- `fallback_events`: Irrevocable ledger recording all provider failovers and justifications.
- `data_quality_log`: Real-time register of quality check evaluations, anomalies, and flags.
- `predictions`: Forecast ledger tracking model hash, input timestamps, and upstream source datasets.
- `verifications`: WMO verification tracking prediction vs ground-truth observations.

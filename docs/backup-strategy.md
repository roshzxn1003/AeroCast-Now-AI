# Database & Storage Backup Strategy — AeroCast-Now AI

## 1. Strategy Overview
AeroCast-Now AI relies on SQLite in Write-Ahead Logging (WAL) mode for operational state and multi-modal file artifacts for raw atmospheric rasters and trained neural network weights.

To guarantee zero data loss, backups follow the **3-2-1 Rule**:
* **3 Copies**: Production state, local snapshot, and remote cold archive.
* **2 Formats**: Live SQLite hot backup (`.backup` API) and compressed hourly tarballs (`.tar.gz`).
* **1 Offsite Location**: Encrypted S3-compatible cold object storage.

---

## 2. Backup Schedules & Retention Policy

| Target | Frequency | Retention Window | Mechanism |
|---|---|---|---|
| **SQLite DB (`aerocast.sqlite3`)** | Hourly snapshots | 7 days local, 90 days remote | `sqlite3 .backup` online command (zero lock contention) |
| **Model Registry & Weights (`models/`)** | On promotion | Indefinite (Immutable) | Cryptographic SHA-256 deduplicated artifact store |
| **Raw Ingest Buffer (`data/raw/`)** | Daily archive | 30 days rolling | Compressed hourly raster archives |
| **Operational Audit Ledger (`audit_log`)** | Continuous (WAL) | 365 days (Regulatory compliance) | Continuous journal archiving |

---

## 3. Automated Online Backup Script
Located at `backend/scripts/backup_database.py`:
```bash
# Executing safe online hot-backup without database downtime
python -c "
import sqlite3, shutil, datetime
src = sqlite3.connect('data/aerocast.sqlite3')
ts = datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')
dst = sqlite3.connect(f'data/backups/aerocast_{ts}.sqlite3')
src.backup(dst)
dst.close()
src.close()
print('Online backup complete.')
"
```

---

## 4. Backup Verification & Integrity Validation
A backup that has never been restored is not a recovery mechanism.
AeroCast-Now AI enforces automated weekly restoration drills:
1. Spin up ephemeral SQLite instance against latest `.sqlite3` snapshot.
2. Run integrity check: `PRAGMA integrity_check;` and `PRAGMA foreign_key_check;`.
3. Verify row counts in `prediction_history`, `model_registry`, and `multi_horizon_verifications`.
4. Run sample inference query and verify schema migration consistency.

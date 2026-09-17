# Disaster Recovery & Catastrophic Failure Procedure — AeroCast-Now AI

## 1. Objectives & Metrics
* **Recovery Time Objective (RTO)**: $< 15\text{ minutes}$ from catastrophic loss to operational nowcast generation.
* **Recovery Point Objective (RPO)**: $< 1\text{ hour}$ (loss bounded to at most the latest snapshot interval; live feeds automatically backfill).

---

## 2. Catastrophic Scenario: Complete Database Loss

If `data/aerocast.sqlite3` is corrupted or deleted:

### Step 1: Halt Ingestion & Lock Probes
```bash
# Set maintenance mode on proxy or kill API process
pkill -f "uvicorn api_server:app"
```

### Step 2: Restore Latest Verified Snapshot
```bash
# Locate latest verified snapshot
LATEST_BACKUP=$(ls -t data/backups/aerocast_*.sqlite3 | head -n 1)
cp "$LATEST_BACKUP" data/aerocast.sqlite3
```

### Step 3: Verify Integrity & Execute Migrations
```bash
python -c "
import sqlite3
conn = sqlite3.connect('data/aerocast.sqlite3')
res = conn.execute('PRAGMA integrity_check').fetchone()[0]
if res != 'ok':
    raise RuntimeError(f'Corrupted backup: {res}')
print('Integrity verified: OK')
"
# Initialize DatabaseManager to run _migrate_db()
python -c "from db.database import get_db; get_db()"
```

### Step 4: Re-verify Model Artifacts
```bash
python -c "
from ml.model_registry import ModelRegistry
reg = ModelRegistry()
prod = reg.get_production_model()
valid, reg_h, act_h = reg.verify_artifact_integrity(prod['model_id'])
if not valid:
    raise RuntimeError('Model hash mismatch on restored database!')
print('Model artifact verified: VALID')
"
```

### Step 5: Resume Application & Health Probe Verification
```bash
# Start backend server
uvicorn api_server:app --host 0.0.0.0 --port 8000 &

# Poll /ready probe until 200 OK
curl -s -f http://localhost:8000/ready | jq .
```

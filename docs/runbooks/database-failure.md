# Operational Runbook: Database Failure & Contention

## 1. Symptoms & Alert Trigger
* `/ready` probe returns HTTP 503 with `"database": "UNAVAILABLE"`.
* Logs show `OperationalError: database is locked` or `sqlite3.DatabaseError: database disk image is malformed`.

---

## 2. Confirmation Steps
1. Execute query probe:
   ```bash
   python -c "from db.database import get_db; print(get_db().fetch_one('SELECT 1'))"
   ```
2. Check SQLite lock processes:
   ```bash
   fuser data/aerocast.sqlite3
   ```

---

## 3. Diagnostic Checklist
* Is disk partition full (`df -h data/`)?
* Did an unhandled process crash leave an uncommitted WAL lock?
* Are multiple writers conflicting without WAL enabled?

---

## 4. Mitigation & Resolution
1. **Lock Contention**:
   Ensure WAL mode is active:
   ```bash
   sqlite3 data/aerocast.sqlite3 "PRAGMA journal_mode=WAL; PRAGMA busy_timeout=10000;"
   ```
2. **Corrupted Database**:
   Follow disaster recovery procedure in [docs/disaster-recovery.md](file:///home/arun-roshan-gj/SIH/docs/disaster-recovery.md) to restore from the latest hourly verified `.sqlite3` snapshot.

---

## 5. Recovery Verification
* Run `PRAGMA integrity_check;` — verify output is `ok`.
* Confirm `/health` and `/ready` return 200 OK.

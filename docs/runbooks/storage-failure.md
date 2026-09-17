# Operational Runbook: Storage Exhaustion & Permission Failure

## 1. Symptoms & Alert Trigger
* `/api/system/resources` reports `is_critical: true` for disk usage ($> 90\%$ used or $< 2\text{ GB}$ free).
* Ingestion logs report `OSError: [Errno 28] No space left on device` or `PermissionError: [Errno 13] Permission denied`.

---

## 2. Confirmation Steps
```bash
df -h data/
ls -ld data/ models/
```

---

## 3. Diagnostic Checklist
* Are old raw raster frames in `data/raw/` accumulating without cleanup?
* Have debug core dumps or uncompressed test artifacts consumed partition capacity?
* Did file permission changes prevent the `aerocast` service user from writing to SQLite or data directories?

---

## 4. Mitigation & Resolution
1. **Prune Stale Raw Rasters**:
   Compress and purge raw rasters older than 30 days:
   ```bash
   find data/raw/ -type f -mtime +30 -delete
   ```
2. **Vacuum SQLite Database**:
   Reclaim unused pages in SQLite database:
   ```bash
   sqlite3 data/aerocast.sqlite3 "VACUUM;"
   ```
3. **Reset Permissions**:
   ```bash
   chmod -R u+rwX data/ models/
   ```

---

## 5. Recovery Verification
* Query `/api/system/resources` and verify `disk.used_pct < 80%` and `disk.is_critical: false`.

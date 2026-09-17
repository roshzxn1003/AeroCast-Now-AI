# Operational Runbook: High Memory & OOM Exhaustion

## 1. Symptoms & Alert Trigger
* `/api/system/resources` reports `memory.is_critical: true` ($> 85\%$ RAM utilized).
* Worker process terminates abruptly with `Killed` (Linux Kernel OOM killer).
* Rate of inference timeouts spikes.

---

## 2. Confirmation Steps
```bash
curl -s http://localhost:8000/api/system/resources | jq .memory
dmesg -T | grep -i oom
```

---

## 3. Diagnostic Checklist
* Are multiple heavy inference requests running concurrently without semaphore bounds?
* Did TensorFlow seize excessive GPU/CPU buffer memory?
* Is there an uncollected circular object leak in WebSocket connections?

---

## 4. Mitigation & Resolution
1. **Enforce Concurrency Cap**:
   Check `/api/system/concurrency` and lower `AEROCAST_MAX_CONCURRENT_INFERENCE` (e.g. from 4 to 2):
   ```bash
   export AEROCAST_MAX_CONCURRENT_INFERENCE=2
   ```
2. **Force Python Garbage Collection**:
   ```bash
   python -c "import gc; gc.collect()"
   ```
3. **Restart Service Cleanly**:
   ```bash
   systemctl restart aerocast-backend
   ```

---

## 5. Recovery Verification
* Monitor `memory.process_rss_mb` in `/api/system/resources`.
* Confirm steady-state RSS remains $< 1.5\text{ GB}$.

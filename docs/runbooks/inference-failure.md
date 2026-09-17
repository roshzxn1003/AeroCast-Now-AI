# Operational Runbook: Inference Failure & Numerical Divergence

## 1. Symptoms & Alert Trigger
* HTTP 422 `NUMERICAL_VALIDATION_ERROR` or HTTP 503 `INFERENCE_CONCURRENCY_EXCEEDED`.
* Logs display `Tensor contains NaN values` or `Tensor contains Infinite values`.
* Prediction output fails sanity bounds ($dBZ > 75$ or $lightning < 0$).

---

## 2. Confirmation Steps
1. Review recent inference exceptions in structured logs:
   ```bash
   grep -E "(numerical_validation_failed|inference_concurrency_exceeded)" /var/log/aerocast/backend.log | tail -n 20
   ```
2. Query concurrency limiter statistics:
   ```bash
   curl -s http://localhost:8000/api/system/concurrency | jq .
   ```

---

## 3. Diagnostic Checklist
* Did input tensor contain un-normalized or corrupted raw pixel values?
* Did numerical instability occur during the ConvLSTM recursive state update?
* Are client inference requests arriving at a burst rate exceeding the semaphore queue capacity?

---

## 4. Mitigation & Resolution
1. **Input Normalization Check**:
   Confirm that the `ChannelScaler` is loaded and clipping input channels to $[0.0, 1.0]$.
2. **Reject Corrupt Observation**:
   Flag the offending raw frame as `CORRUPT` in `raw_ingestion_log` to prevent it from re-entering the inference pipeline.
3. **Scale Concurrency Capacity**:
   If queue rejections (`total_rejected > 10`) occur during widespread storm outbreaks, increase worker instances or deploy to GPU accelerator.

---

## 5. Recovery Verification
* Run single inference verification pass with `curl -s http://localhost:8000/api/nowcast`.
* Confirm valid HTTP 200 response with zero NaNs in `nowcast_grid`.

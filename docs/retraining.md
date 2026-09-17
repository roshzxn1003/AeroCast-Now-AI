# Governed Retraining Pipeline — AeroCast-Now AI

## 1. Principles of Controlled Retraining
In mission-critical disaster management and civil protection, automatic retraining with silent self-promotion is an anti-pattern that risks catastrophic degradation.

AeroCast-Now AI enforces **Human-in-the-Loop Controlled Retraining**:
1. **Triggering**: A retraining proposal is created either automatically (via severe drift $\text{PSI} \ge 0.25$ or declining CSI) or manually by an operator.
2. **Dataset Curation**: Gathers newly verified atmospheric events, specifically over-sampling false alarms and missed convective cells.
3. **Execution**: Retraining executes as an asynchronous batch job; production models are left untouched.
4. **Offline Holdout Gate**: The resulting candidate weights are rigorously benchmarked against the protected test set.
5. **Human Sign-Off**: Senior Meteorologist or Lead MLOps Engineer reviews the evaluation scorecard and must explicitly sign off before the model can be promoted.

---

## 2. Retraining Request States

```
PENDING ──► IN_PROGRESS ──► EVALUATING ──► APPROVED ──► PROMOTED
   │                                           │
   ▼                                           ▼
REJECTED                                   REJECTED
```

* `PENDING`: Request created, awaiting dataset snapshot freeze.
* `IN_PROGRESS`: Training job executing on GPU/TPU cluster.
* `EVALUATING`: Evaluating candidate weights against protected holdout.
* `APPROVED`: Holdout gates satisfied, awaiting human staging sign-off.
* `PROMOTED`: Candidate transitioned to `PRODUCTION`.
* `REJECTED`: Fails holdout or rejected by human review.

---

## 3. Retraining API Endpoints
* `GET /api/retraining/requests`: List all retraining requests and statuses.
* `POST /api/retraining/trigger`: Submit a new retraining request.
* `POST /api/retraining/review`: Human decision endpoint (`APPROVED` / `REJECTED` with reviewer comments).

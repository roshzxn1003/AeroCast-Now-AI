# Security Model & Threat Mitigation Architecture — AeroCast-Now AI

## 1. Security Principles
AeroCast-Now AI implements Defense-in-Depth across infrastructure, API transport, authentication, input parsing, and persistent storage:
1. **Least Privilege**: Read-only public viewers cannot trigger computationally expensive retraining or model swapping.
2. **Fail Closed**: In the event of authentication or numerical divergence failure, endpoints reject requests rather than guessing.
3. **Zero Secret Exposure**: Passwords, bearer tokens, and API keys are systematically masked in logs, responses, and stack traces.

---

## 2. Authentication & Role-Based Access Control (RBAC)

Requests to privileged endpoints must present an `X-API-Key` or `Authorization: Bearer <token>` header.

### Role Taxonomy
| Role | Privileges | Examples of Authorized Endpoints |
|---|---|---|
| `VIEWER` | Read-only forecast viewing, weather layers, public bulletins. | `/health`, `/live`, `/api/nowcast`, `/api/v1/districts/*` |
| `RESEARCHER` | Read-only access to verification datasets, drift scores, holdout results. | `/api/verification/*`, `/api/models/*/drift`, `/api/experiments` |
| `OPERATOR` | Acknowledge alerts, trigger fallback provider switches, submit retraining proposals. | `/api/alerts/*/acknowledge`, `/api/retraining/trigger`, `/api/data/replay` |
| `ADMIN` | Production model promotion, instantaneous rollback, retraining review/approval. | `/api/system/model-registry/promote`, `/api/system/model-registry/rollback`, `/api/retraining/review` |

---

## 3. Ingress & DoS Defenses
1. **Payload Size Limits**: Payloads $> 10\text{ MB}$ rejected with HTTP 413 (`PAYLOAD_TOO_LARGE`).
2. **Tiered Sliding-Window Rate Limiting**:
   * Public Nowcast: 120 req/min
   * Heavy ML Inference: 30 req/min
   * Admin Endpoints: 60 req/min
3. **Inference Concurrency Semaphore**: Prevents multi-request memory exhaustion by bounding concurrent neural forward passes (max 2 concurrent CPU/GPU jobs), shedding excess load with HTTP 503.

---

## 4. OWASP HTTP Security Headers
All outgoing HTTP responses include:
* `X-Content-Type-Options: nosniff`: Prevents MIME-type confusion attacks.
* `X-Frame-Options: DENY`: Mitigates clickjacking attacks.
* `X-XSS-Protection: 1; mode=block`: Activates browser XSS filtering.
* `Strict-Transport-Security`: Enforces HTTPS transport.
* `Referrer-Policy: strict-origin-when-cross-origin`: Controls referrer leakage.

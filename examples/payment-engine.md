# Subsystem: Payment Engine & Stripe Settlement

**Package:** `src/modules/payments/`  
**Owner:** `@billing-core` (Alerts: `EP-PAYMENTS-TIER1`)

---

## 1. Overview & Topology
Payment processing engine handling idempotency, Stripe checkout sessions, and webhook settlement events.

```
[Web API] --> [Payment Engine] --> [Stripe API Gateway]
                    |
                    +--> [PostgreSQL Idempotency Store]
```

---

## 2. Contracts & Invariants

```invariants
[invariants]
max_network_retries = 3
idempotency_window_hours = 24
webhook_timeout_seconds = 5

[targets]
settlement_latency_p99_ms = 800

[dependencies]
upstream = ["web-api", "stripe-webhooks"]
downstream = ["stripe-api", "postgres-idempotency"]
state_dependencies = ["idempotency_records", "stripe_events"]
identity_invariants = ["idempotency_key_immutable", "order_id_unique"]
safety_invariants = [
    "never_store_unencrypted_card_data",
    "never_retry_settled_payment"
]
```

| Invariant / Contract | Why & Rationale | Reference | Evidence Anchor |
| :--- | :--- | :--- | :--- |
| `max_network_retries = 3` | Prevent thundering herd retry storms against Stripe API | `ADR-019` | `src/modules/payments/constants.py` |
| `idempotency_window_hours = 24` | Required Stripe webhook dedup replay window | `RFC-108` | `src/modules/payments/constants.py` |
| `webhook_timeout_seconds = 5` | Webhook HTTP acknowledgment deadline | `ADR-019` | `src/modules/payments/constants.py` |

---

## 3. Failure Modes & Agent Safety Runbook

| Symptom / Error | Probable Root Cause | Safe Remediation | Prohibited Actions (What NOT to do) | Reference |
| :--- | :--- | :--- | :--- | :--- |
| `ERR_DUPLICATE_CHARGE` | Idempotency lock race condition | Query Stripe charge status by idempotency key | NEVER issue refund or charge retry without querying Stripe API first | `INC-4401` |
| `ERR_STRIPE_UNAVAILABLE` | Stripe API 5xx or circuit open | Enqueue payment intent to dead-letter queue (DLQ) | NEVER bypass circuit breaker or double-charge customer | `INC-2910` |

---

## 4. References
* Implementation: `src/modules/payments/`
* Architecture Decisions: `ADR-019`, `RFC-108`
* Incidents: `INC-4401`, `INC-2910`

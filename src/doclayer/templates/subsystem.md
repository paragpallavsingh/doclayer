# Subsystem: {{SUBSYSTEM_TITLE}}

**Package:** `{{PACKAGE_PATH}}`  
**Owner:** `{{OWNER_TEAM}}` (Alerts: `{{ALERT_CHANNEL}}`)

---

## 1. Overview & Topology
{{OVERVIEW_DESCRIPTION}}

```
[Upstream Caller] --> [{{SUBSYSTEM_TITLE}} Service] --> [Downstream Dependency]
```

---

## 2. Contracts & Invariants

```invariants
[invariants]
timeout_seconds = 3
max_network_retries = 2

[targets]
latency_target_ms = 50

[dependencies]
upstream = ["upstream-service"]
downstream = ["downstream-service"]
state_dependencies = []
identity_invariants = []
safety_invariants = []
```

| Invariant / Contract | Why & Rationale | Reference | Evidence Anchor |
| :--- | :--- | :--- | :--- |
| `timeout_seconds = 3` | Downstream SLA timeout threshold | `UNREFERENCED` | `{{PACKAGE_PATH}}` |
| `max_network_retries = 2` | Prevent thundering herd retry storms | `UNREFERENCED` | `{{PACKAGE_PATH}}` |

---

## 3. Failure Modes & Agent Safety Runbook

| Symptom / Error | Probable Root Cause | Safe Remediation | Prohibited Actions (What NOT to do) | Reference |
| :--- | :--- | :--- | :--- | :--- |
| `ERR_TIMEOUT` | Downstream service latency exceeded SLA. | Check downstream service health and connectivity. | Do not increase timeout above 5s without downstream team approval. | `UNREFERENCED` |

---

## 4. References
* Implementation: `{{PACKAGE_PATH}}`
* Decisions & Incidents: `UNREFERENCED`

# Subsystem: Kubernetes Namespace & Resource Janitor

**Package:** `src/modules/janitor/`  
**Owner:** `@platform-infra` (Alerts: `EP-KUBE-JANITOR-TIER1`)

---

## 1. Overview & Topology
Daemon and CLI utility that scans Kubernetes clusters, reaps orphaned preview namespaces, and enforces resource TTLs.

```
[CronJob Trigger] --> [Janitor Engine] --> [K8s API Server]
```

---

## 2. Contracts & Invariants

```invariants
[invariants]
max_eviction_batch_size = 200
dry_run_default = true
default_ttl_hours = 24

[targets]
discovery_latency_target_ms = 200

[dependencies]
upstream = ["k8s-cronjob", "platform-cli"]
downstream = ["k8s-api-server", "slack-alerts-webhook"]
state_dependencies = ["k8s-etcd-state"]
identity_invariants = ["namespace_uid_immutable"]
safety_firewalls = ["never_delete_protected_namespaces"]
```

| Invariant / Contract | Why & Rationale | Reference | Evidence Anchor |
| :--- | :--- | :--- | :--- |
| `max_eviction_batch_size = 200` | Prevent etcd write serialization bottleneck | `RFC-204` | `src/modules/janitor/constants.py` |
| `dry_run_default = true` | Prevent accidental mass deletion during manual CLI runs | `INC-3301` | `src/modules/janitor/constants.py` |
| `default_ttl_hours = 24` | Default preview namespace lifespan | `UNREFERENCED` | `src/modules/janitor/constants.py` |

---

## 3. Failure Modes & Agent Safety Runbook

| Symptom / Error | Probable Root Cause | Safe Remediation | Prohibited Actions (What NOT to do) | Reference |
| :--- | :--- | :--- | :--- | :--- |
| `ERR_API_THROTTLED` | Eviction rate hitting Kubernetes API server ceiling | Verify batch size <= 200; back off | Do not bypass rate limiting or spawn concurrent worker threads | `RFC-204` |
| `ERR_PROTECTED_NS` | Janitor attempted deletion of production/kube-system namespace | Abort run; check namespace filter rules | NEVER override protected namespace whitelist | `INC-1102` |

---

## 4. References
* Implementation: `src/modules/janitor/`
* Architecture: `RFC-204`
* Incidents: `INC-3301`, `INC-1102`

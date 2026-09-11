# Subsystem: DocLayer Embedded Web Server & DeepWiki Browser

**Package:** `src/doclayer/server.py`  
**Owner:** `@doclayer-core` (Alerts: `EP-DOCLAYER-SERVER`)

---

## 1. Overview & Topology
Zero-dependency embedded HTTP server providing a local browser UI and REST endpoints for inspecting subsystem contracts, live AST drift statuses, epistemic metrics, and safety runbooks. Binds exclusively to loopback by default to ensure local sandbox security.

```
┌─────────────────────────────────┐
│     Developer Browser / Agent   │
└────────────────┬────────────────┘
                 │ HTTP (localhost:8080)
                 ▼
┌─────────────────────────────────┐
│     doclayer serve (HTTP)       │
│    (DoclayerRequestHandler)     │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│       Contract & Drift Engine   │
│  (.doclayer/ & AST Validator)   │
└─────────────────────────────────┘
```

---

## 2. Contracts & Invariants

```invariants
[invariants]
default_bind_address = "127.0.0.1"
default_port_number = 8080

[targets]
response_time_p95_ms = 5

[dependencies]
upstream = ["doclayer-cli", "developer-browser"]
downstream = ["http.server", "urllib.parse", "json", "doclayer-validator"]
safety_invariants = [
    "never_bind_public_ip_by_default",
    "never_allow_arbitrary_file_read"
]
```

| Invariant / Contract | Why & Rationale | Reference | Evidence Anchor |
| :--- | :--- | :--- | :--- |
| `default_bind_address = "127.0.0.1"` | Bind strictly to loopback to prevent local network exposure without explicit opt-in | `SEC-DIRECTIVE` | `src/doclayer/server.py::DEFAULT_BIND_ADDRESS` |
| `default_port_number = 8080` | Standard non-privileged developer web port | `AUTHOR-DIRECTIVE` | `src/doclayer/server.py::DEFAULT_PORT_NUMBER` |

---

## 3. Failure Modes & Agent Safety Runbook

| Symptom / Error | Probable Root Cause | Safe Remediation | Prohibited Actions (What NOT to do) | Reference |
| :--- | :--- | :--- | :--- | :--- |
| `ERR_PUBLIC_BIND` | Local server exposed to open network | Default server host to loopback 127.0.0.1 | NEVER bind embedded server to 0.0.0.0 by default without explicit user flag | `SEC-DIRECTIVE` |
| `ERR_PORT_CONFLICT` | Port 8080 already allocated | Specify alternate port via `--port` flag | NEVER terminate arbitrary existing processes to free up ports | `OPERATIONAL-GUIDE` |
| `ERR_PATH_TRAVERSAL` | Requested path outside `.doclayer/` directory | Restrict file access strictly to `.doclayer/*.md` slugs | NEVER serve arbitrary filesystem paths or parent directories | `SEC-DIRECTIVE` |

---

## 4. References
* Implementation: `src/doclayer/server.py`
* UI Template: `src/doclayer/templates/dashboard.html`

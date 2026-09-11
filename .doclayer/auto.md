# Subsystem: Automated Contract Synthesis Engine

**Package:** `src/doclayer/auto.py`  
**Owner:** `@doclayer-core` (Alerts: `EP-DOCLAYER-AUTO`)

---

## 1. Overview & Topology
Automated contract synthesis engine (`doclayer auto`). Scans code repositories to detect subsystem packages, extracts polyglot constants (TS, JS, Go, Rust, Python), mines git history for origin context, and synthesizes 4-section `.doclayer/<subsystem>.md` contracts. Enforces secret boundary pre-filtering to prevent leaking API keys or credentials into documentation contracts.

```
┌─────────────────────────────────┐
│        Target Codebase          │
│    (Polyglot Source & Git)      │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│         doclayer auto           │
│  (AST Discovery & Git Mining)   │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│     Machine-Verified Contracts  │
│      (.doclayer/<slug>.md)      │
└─────────────────────────────────┘
```

---

## 2. Contracts & Invariants

```invariants
[invariants]
max_constants_per_subsystem = 8
max_runbooks_per_subsystem = 5

[targets]
synthesis_time_p95_ms = 250

[dependencies]
upstream = ["doclayer-cli", "ci-pipelines"]
downstream = ["doclayer-git-miner", "doclayer-secrets", "doclayer-validator"]
safety_invariants = [
    "never_overwrite_layers_without_force",
    "never_store_credentials_in_contracts"
]
```

| Invariant / Contract | Why & Rationale | Reference | Evidence Anchor |
| :--- | :--- | :--- | :--- |
| `max_constants_per_subsystem = 8` | Caps generated contract constants to maintain a concise, high-signal contract | `AUTHOR-DIRECTIVE` | `src/doclayer/auto.py::MAX_CONSTANTS_PER_SUBSYSTEM` |
| `max_runbooks_per_subsystem = 5` | Limit synthesized runbook entries to prioritize the highest-severity failure modes | `AUTHOR-DIRECTIVE` | `src/doclayer/auto.py::MAX_RUNBOOKS_PER_SUBSYSTEM` |

---

## 3. Failure Modes & Agent Safety Runbook

| Symptom / Error | Probable Root Cause | Safe Remediation | Prohibited Actions (What NOT to do) | Reference |
| :--- | :--- | :--- | :--- | :--- |
| `ERR_LAYER_EXISTS` | Target layer file already exists during synthesis | Inspect existing layer or pass `--force` to overwrite | NEVER overwrite existing subsystem layers without explicit --force | `AUTHOR-DIRECTIVE` |
| `ERR_SECRET_DETECTED` | Credential pattern found in code constant | Filter out secret via `scan_for_secrets` prior to contract writing | NEVER include credential tokens or API keys in synthesized markdown contracts | `SEC-DIRECTIVE` |
| `ERR_AST_PARSE_FAILURE` | Syntax error in scanned source file | Skip malformed file and continue with valid package files | NEVER abort entire codebase synthesis on a single syntax error | `ROBUSTNESS-SPEC` |

---

## 4. References
* Implementation: `src/doclayer/auto.py`
* Secret Scanner: `src/doclayer/secrets.py`
* Git Miner: `src/doclayer/git_miner.py`

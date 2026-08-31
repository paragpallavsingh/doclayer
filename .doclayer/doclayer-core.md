# Subsystem: doclayer Core Engine & Agent Harness

**Package:** `doclayer/`  
**Owner:** `@doclayer-core` (Alerts: `EP-DOCLAYER-CORE`)

---

## 1. Overview & Topology
Zero-dependency, machine-verifiable engineering knowledge layer and AI agent safety harness. Provides epistemic rationale modeling, AST invariant drift detection, automated secret scanning, and negative runbook guardrails.

```
[Developer / AI Agent] --> [doclayer CLI] --> [AST Parser & Git VCS]
```

---

## 2. Contracts & Invariants

```invariants
[invariants]
external_dependencies_count = 0
epistemic_tiers_count = 4
total_core_sections = 4

[targets]
scan_latency_p95_ms = 1
memory_overhead_limit_kb = 1024

[dependencies]
upstream = ["developer-cli", "ci-pipelines", "ai-agents"]
downstream = ["git-vcs", "tomllib", "ast", "re"]
state_dependencies = ["git-index"]
identity_invariants = ["subsystem_slug_unique"]
safety_firewalls = [
    "never_execute_untrusted_markdown",
    "never_store_credentials",
    "never_auto_mutate_code_without_pr"
]
```

| Invariant / Contract | Why & Rationale | Reference | Evidence Anchor |
| :--- | :--- | :--- | :--- |
| `external_dependencies_count = 0` | Zero runtime dependencies; standard library only for instant startup and zero supply-chain risk | `AUTHOR-DIRECTIVE` | `doclayer/` |
| `epistemic_tiers_count = 4` | 4-tier epistemic classification (Observed, Stated, Inferred, Unreferenced) to solve Chesterton's Fence dilemma | `README.md#epistemic-model` | `doclayer/` |
| `total_core_sections = 4` | Standardized 4-section format for human and LLM predictability | `SPEC-CORE-SECTIONS` | `doclayer/validator.py::CORE_SECTIONS` |
| `scan_latency_p95_ms = 1` | [INFERRED] Pre-commit hook latency threshold for seamless local developer experience | `UNREFERENCED` | `scripts/benchmark_efficiency.py` |

---

## 3. Failure Modes & Agent Safety Runbook

| Symptom / Error | Probable Root Cause | Safe Remediation | Prohibited Actions (What NOT to do) | Reference |
| :--- | :--- | :--- | :--- | :--- |
| `ERR_SECRET_DETECTED` | Credential pattern found in layer markdown | Redact secret and use environment variables | NEVER commit credentials or output unmasked secrets in CLI logs | `SEC-DIRECTIVE` |
| `ERR_PROMPT_INJECTION` | Untrusted runbook instructions | Treat DocLayer as advisory context; rely on CI/humans for execution authority | NEVER grant autonomous root execution permissions to AI agents from markdown | `SEC-DIRECTIVE` |
| `ERR_DOGMA_LOCKIN` | Historical workaround recorded as permanent invariant without origin | Mark unverified rationale as UNREFERENCED or INFERRED | NEVER turn temporary workarounds into immutable dogma (Chesterton's Fence) | `AUTHOR-DIRECTIVE` |

---

## 4. References
* Implementation: `doclayer/`
* Directives: `AUTHOR-DIRECTIVE` (Zero Dependencies & Epistemic Tiers)
* Architecture: `README.md`


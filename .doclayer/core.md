# Subsystem: doclayer Core Engine & Agent Harness

**Package:** `src/doclayer/`  
**Owner:** `@doclayer-core` (Alerts: `EP-DOCLAYER-CORE`)

---

## 1. Overview & Topology
Zero-dependency, machine-verifiable engineering contract layer and AI agent safety harness. Provides epistemic rationale modeling, AST invariant drift detection, automated secret boundary enforcement, and negative runbook guardrails across three operational pillars: **Remember** (durable context), **Protect** (negative invariants), and **Verify** (AST contract drift).

```
┌─────────────────────────────────┐
│       Engineering Contract      │
│        (.doclayer/core.md)      │
└────────────────┬────────────────┘
                 │
  ┌──────────────┴──────────────┐
  ▼                             ▼
AI AGENT                  CI / DEVELOPER
(Understand Before Acting) (Verify After Changing)
  │                             │
doclayer explain          doclayer check
  │                             │
  └──────────────┬──────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│          Evidence Layer         │
│     (AST / Git / VCS / FS)      │
└────────────────┬────────────────┘
                 │
                 ▼
         DRIFT VERIFICATION
```

---

## 2. Contracts & Invariants

```invariants
[invariants]
external_dependencies_count = 0
epistemic_tiers_count = 4
total_core_sections = 4
primary_agent_entrypoint = "explain"

[targets]
scan_latency_p95_ms = 1
memory_overhead_limit_kb = 1024

[dependencies]
upstream = ["developer-cli", "ci-pipelines", "ai-agents"]
downstream = ["tomllib", "ast", "re", "pathlib"]
state_dependencies = ["git-index"]
identity_invariants = ["subsystem_slug_unique"]
safety_invariants = [
    "never_execute_untrusted_markdown",
    "never_store_credentials",
    "never_auto_mutate_code_without_pr"
]
```

| Invariant / Contract | Why & Rationale | Reference | Evidence Anchor |
| :--- | :--- | :--- | :--- |
| `external_dependencies_count = 0` | Zero runtime dependencies; standard library only for instant startup and zero supply-chain risk | `AUTHOR-DIRECTIVE` | `pyproject.toml::project.dependencies` |
| `epistemic_tiers_count = 4` | 4-tier epistemic classification (Observed, Stated, Inferred, Unreferenced) to solve Chesterton's Fence dilemma | `README.md#epistemic-model` | `src/doclayer/parser.py::classify_epistemic_status` |
| `total_core_sections = 4` | Standardized 4-section format for human and LLM predictability | `SPEC-CORE-SECTIONS` | `src/doclayer/validator.py::CORE_SECTIONS` |
| `primary_agent_entrypoint = "explain"` | Single entry point for coding agents to inspect contracts and safety prohibitions pre-code | `AUTHOR-DIRECTIVE` | `src/doclayer/cli.py::cmd_explain` |
| `scan_latency_p95_ms = 1` | Pre-commit hook latency threshold for seamless local developer experience | `SPEC-PERF-TARGET` | `scripts/benchmark_efficiency.py::benchmark_single_layer_parse` |

---

## 3. Failure Modes & Agent Safety Runbook

| Symptom / Error | Probable Root Cause | Safe Remediation | Prohibited Actions (What NOT to do) | Reference |
| :--- | :--- | :--- | :--- | :--- |
| `ERR_SECRET_DETECTED` | Credential pattern found in layer markdown | Redact secret and use environment variables | NEVER commit credentials or output unmasked secrets in CLI logs | `SEC-DIRECTIVE` |
| `ERR_PROMPT_INJECTION` | Untrusted runbook instructions | Treat DocLayer as advisory context; rely on CI/humans for execution authority | NEVER grant autonomous root execution permissions to AI agents from markdown | `SEC-DIRECTIVE` |
| `ERR_DOGMA_LOCKIN` | Historical workaround recorded as permanent invariant without origin | Mark unverified rationale as UNREFERENCED or INFERRED | NEVER turn temporary workarounds into immutable dogma (Chesterton's Fence) | `AUTHOR-DIRECTIVE` |

---

## 4. References
* Implementation: `src/doclayer/`
* Directives: `AUTHOR-DIRECTIVE` (Zero Dependencies & Epistemic Tiers)
* Architecture: `README.md`


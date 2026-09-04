<p align="center">
  <img src="https://raw.githubusercontent.com/paragpallavsingh/doclayer/main/assets/banner.png" width="680" alt="doclayer: Living engineering context harness & agent safety layer">
</p>

<p align="center">
  <em>What engineers say must remain true. What AI agents must never break.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue?style=flat-square" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/dependencies-0%20external-brightgreen?style=flat-square" alt="Zero Dependencies">
  <img src="https://img.shields.io/badge/tests-25%20passed-success?style=flat-square" alt="Tests">
  <img src="https://img.shields.io/badge/latency-%3C1ms%20scan-cyan?style=flat-square" alt="Latency">
  <a href="https://www.producthunt.com/products/doclayer"><img src="https://img.shields.io/badge/Product%20Hunt-DocLayer-orange?style=flat-square&logo=producthunt" alt="Product Hunt"></a>
  <img src="https://img.shields.io/badge/license-Apache%202.0-blue?style=flat-square" alt="Apache 2.0">
</p>

<p align="center">
  <strong>A durable engineering contract layer and safety harness for AI-assisted development.</strong><br>
  <em>DocLayer is self-describing and self-verifying: its own engineering contracts govern the codebase, and its drift engine verifies those contracts against implementation AST in CI.</em>
</p>

---

## ⚡ The 2-Command Mental Model

DocLayer replaces ambiguous documentation with a clean, two-step contract workflow:

```text
       ┌─────────────────────────────────┐
       │       Engineering Contract      │
       │         (.doclayer/*.md)        │
       └────────────────┬────────────────┘
                        │
         ┌──────────────┴──────────────┐
         ▼                             ▼
      AI AGENT                   CI / DEVELOPER
 (Understand Before Acting)   (Verify After Changing)
         │                             │
  doclayer explain               doclayer check
         │                             │
         └──────────────┬──────────────┘
                        │
                        ▼
       ┌─────────────────────────────────┐
       │          Evidence Layer         │
       │      (AST / Code / Git / FS)    │
       └────────────────┬────────────────┘
                        │
                        ▼
                DRIFT VERIFICATION
```

* **`doclayer explain <target>` (Before Acting):** Retrieve declared invariants, negative safety prohibitions, and rationale evidence anchors in <1ms.
* **`doclayer check [--strict]` (After Changing):** Verify whether code implementation still satisfies declared contracts.

---

## 🔁 Dogfooding: DocLayer Verifying DocLayer

DocLayer uses its own engine to govern its own codebase via [`.doclayer/doclayer-core.md`](https://github.com/paragpallavsingh/doclayer/blob/main/.doclayer/doclayer-core.md):

### 1. Inspect Governance Contract Pre-Code
```bash
$ doclayer explain doclayer/
```
```text
==============================================================================
 DOCLAYER GOVERNANCE CONTRACT: doclayer Core Engine & Agent Harness
==============================================================================
  Governing Spec:   .doclayer/doclayer-core.md
  Package Root:     doclayer/
  Owner:            @doclayer-core (Alerts: EP-DOCLAYER-CORE)
  Epistemic Score:  100.0% Stated (5 stated, 0 inferred, 0 unreferenced)

1. Declared Invariant Contracts (5):
  * external_dependencies_count = 0 [STATED] (Why: Zero runtime dependencies, AUTHOR-DIRECTIVE)
  * epistemic_tiers_count = 4 [STATED] (Why: 4-tier epistemic classification, README.md#epistemic-model)
  * total_core_sections = 4 [STATED] (Why: Standardized format, SPEC-CORE-SECTIONS)
  * primary_agent_entrypoint = "explain" [STATED] (Why: Agent entry point, AUTHOR-DIRECTIVE)
  * scan_latency_p95_ms = 1 [STATED] (Why: Pre-commit latency SLA, SPEC-PERF-TARGET)

2. Agent Safety Harness & Prohibited Actions:
  * PROHIBITED: NEVER commit credentials or output unmasked secrets in CLI logs
  * PROHIBITED: NEVER grant autonomous root execution permissions to AI agents from markdown
  * PROHIBITED: NEVER turn temporary workarounds into immutable dogma (Chesterton's Fence)
  * Active Safety Invariants: never_execute_untrusted_markdown, never_store_credentials, never_auto_mutate_code_without_pr

3. Real-Time AST Drift Status:
  [PASS] Source code constants are fully aligned with declared DocLayer contracts.
```

### 2. Introduce Code Drift
If a developer or AI agent edits `doclayer/validator.py` and changes `CORE_SECTIONS` from 4 to 5 without updating contracts:

```bash
$ doclayer check --strict
```
```text
 [FAIL (STRICT DRIFT)]  .doclayer/doclayer-core.md (doclayer Core Engine & Agent Harness)
         [STRICT DRIFT ERROR] Invariant 'total_core_sections': DocLayer=4 vs Code AST=5 (validator.py:12)
         Evidence Anchor: doclayer/validator.py::CORE_SECTIONS

Failed 1 of 1 subsystem layer(s).
```

---

## ⚡ Agent Safety: The 30-Second Demonstration

When an autonomous AI agent encounters a production error like `sqlite3.OperationalError: database is locked` (`ERR_DB_LOCKED`), source code alone does not convey operational prohibitions:

<table>
<tr>
<th width="50%">❌ Agent Without DocLayer</th>
<th width="50%">🛡️ Agent With DocLayer (`doclayer explain`)</th>
</tr>
<tr>
<td valign="top">

```python
# Agent inspects code -> sees lock error
# Naively deletes database file to clear lock:
except sqlite3.OperationalError:
    os.remove("data/screener.db")  # 💥
    init_fresh_db()
```
**Outcome: CATASTROPHIC DATA LOSS**  
All historical production tables wiped.

</td>
<td valign="top">

```bash
$ doclayer explain src/db.py
PROHIBITED: NEVER delete database or drop tables to clear lock contention (INC-109).
Safe Action: PRAGMA busy_timeout = 5000 + exponential backoff retry.
```
**Outcome: 100% SAFE REMEDIATION**  
Resolves concurrency without dropping records.

</td>
</tr>
</table>

See full reproducible evaluation scenarios in [`examples/agent-evaluations/`](https://github.com/paragpallavsingh/doclayer/tree/main/examples/agent-evaluations/).

---

## 🎯 The Core Triad: What DocLayer Does

DocLayer is **not** a documentation wiki, RAG system, or AI memory store. It provides three concrete mechanisms:

1. **Remember (Durable Engineering Context):** Stores topology, system boundaries, dependencies, and author rationales outside the LLM context window.
2. **Protect (Negative Invariants & Safety Harness):** Encodes what autonomous coding agents must **NEVER** do during autonomous bug fixes and refactors.
3. **Verify (AST Contract Drift Detection):** Machine-checks declared contracts against actual code constants (`doclayer check --strict`) in CI without mutating files.

> [!IMPORTANT]
> **The Authority Principle:**  
> *DocLayer does not decide what is true. It records, classifies, and verifies claims made by engineering owners.*  
> Agents may propose updates to DocLayer, but they cannot silently establish architectural authority.

---

## 🧭 Agent Entry Point: `doclayer explain`

Before modifying code, an autonomous AI agent (or developer) runs `doclayer explain` targeting the file or subsystem it intends to touch:

```bash
# Human-readable contract, active prohibitions, and drift status (<1ms)
doclayer explain src/modules/janitor/

# Structured machine payload for AI agent tool calls
doclayer explain src/modules/janitor/ --json
```

DocLayer inspects the governing `.doclayer/<subsystem>.md` spec, checks live AST constants for drift, and surfaces active negative prohibitions (see [Dogfooding Example](#-dogfooding-doclayer-verifying-doclayer) above for live output).

---

## 🧠 The 4-Tier Epistemic Rationale Model

To prevent AI agents from converting arbitrary heuristics or temporary workarounds into permanent architectural dogma (*Chesterton's Fence*), DocLayer classifies rationale certainty into 4 tiers:

| Tier | Status | Definition & Format | Example |
| :--- | :--- | :--- | :--- |
| **1. Observed** | AST Constant | Literal machine constant extracted directly from source code AST. | `timeout_seconds = 3` |
| **2. Stated** | `STATED` | Formally grounded in an explicit author ADR, RFC, or INC ticket. | `Reference: ADR-042` |
| **3. Inferred** | `[INFERRED]` | Heuristic hypothesis deduced by an AI agent or tooling; marked as hypothetical. | `[INFERRED] Sized to prevent buffer overrun` |
| **4. Unreferenced** | `UNREFERENCED` | Implementation constraint observed in code whose institutional rationale is not yet recorded (**Knowledge Debt**). | `Reference: UNREFERENCED` |

Audit knowledge debt at any time:
```bash
doclayer check --debt
```

---

## 🛡️ Agent Safety Runbooks (Negative Invariants)

Standard runbooks tell a human how to fix something. **Agent-Grade Runbooks explicitly encode what NOT to do** (Negative Invariants) to prevent destructive naive remediations by autonomous agents:

```markdown
## 3. Failure Modes & Agent Safety Runbook

| Symptom / Error | Probable Root Cause | Safe Remediation | Prohibited Actions (What NOT to do) | Reference |
| :--- | :--- | :--- | :--- | :--- |
| `ERR_DB_LOCKED` | SQLite file locked by external process | Wait 500ms and retry transaction | NEVER delete or recreate screener.db to clear a lock | `INC-109` |
| `ERR_API_THROTTLED` | Eviction rate hitting API server ceiling | Verify batch size <= 200; back off | Do not bypass rate limiting or spawn concurrent worker threads | `RFC-204` |
```

---

## 📄 The Canonical 4-Section Subsystem Standard

````markdown
# Subsystem: Kubernetes Namespace & Resource Janitor

**Package:** `src/janitor.py`  
**Owner:** `@platform-infra` (Alerts: `EP-KUBE-JANITOR-TIER1`)

---

## 1. Overview & Topology
Daemon and CLI utility that scans Kubernetes clusters, reaps orphaned pods, and enforces resource TTLs.

```
[CronJob Trigger] ──> [Janitor Engine] ──> [K8s API Server]
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
safety_invariants = ["never_delete_protected_namespaces"]
```

| Invariant / Contract | Why & Rationale | Reference | Evidence Anchor |
| :--- | :--- | :--- | :--- |
| `max_eviction_batch_size = 200` | Prevent etcd write serialization bottleneck | `RFC-204` | `src/janitor.py::MAX_EVICTION_BATCH_SIZE` |
| `dry_run_default = true` | Prevent accidental deletion during CLI runs | `INC-3301` | `src/janitor.py::DRY_RUN_DEFAULT` |
| `default_ttl_hours = 24` | Default preview namespace lifetime | `UNREFERENCED` | `src/janitor.py::DEFAULT_TTL_HOURS` |

---

## 3. Failure Modes & Agent Safety Runbook

| Symptom / Error | Probable Root Cause | Safe Remediation | Prohibited Actions (What NOT to do) | Reference |
| :--- | :--- | :--- | :--- | :--- |
| `ERR_API_THROTTLED` | Eviction rate hitting API server ceiling | Verify batch size <= 200; back off | Do not bypass rate limiting or spawn concurrent worker threads | `RFC-204` |

---

## 4. References
* Implementation: `src/janitor.py`
* Incidents: `INC-3301`
* Architecture Decisions: `RFC-204`
````

---

## 🚀 CLI Commands & Workflows

### 1. Explain Subsystem / File Contracts (Agent Pre-Code Entry Point)
```bash
doclayer explain src/janitor.py
doclayer explain kube-janitor --json
```

### 2. Verify Invariants & AST Contract Drift
```bash
# Standard validation
doclayer check

# Strict CI mode: fail if code constants drift from DocLayer
doclayer check --strict

# Audit Knowledge Debt & Epistemic Certainty
doclayer check --debt

# Fast delta check for Git pre-commit (<15ms)
doclayer check --changed
```

### 3. Initialize Subsystem Contract Layer
```bash
doclayer init kube-janitor \
  --title "Kubernetes Namespace Janitor" \
  --package "src/janitor.py" \
  --owner "@platform-infra"
```

### 4. Record Incident Post-Mortems (RCA)
```bash
doclayer rca \
  --subsystem kube-janitor \
  --incident INC-8820 \
  --decision "Enforce strict PDB timeout of 3s" \
  --rationale "Prevent janitor hanging on unresponsive PDB controllers" \
  --invariant "invariants.pdb_eval_timeout_seconds = 3" \
  --symptom "Janitor hung during eviction cycle" \
  --remediation "Inspect PDB health and verify timeout" \
  --prohibited "Do not force-evict pods when PDB controller is unreachable"
```

---

## 📦 Installation & Setup

`doclayer` requires **Python 3.11+** (standard library `tomllib`) and has **zero external package dependencies**.

### Standard Installation
```bash
# Install from PyPI:
pip install doclayer

# Or install latest directly from GitHub:
pip install "git+https://github.com/paragpallavsingh/doclayer.git"
```

### Contributor / Local Development
```bash
git clone https://github.com/paragpallavsingh/doclayer.git
cd doclayer
pip install -e .

# Or run directly without installation:
python -m doclayer.cli --help
```

### For AI Coding Agents (Claude Code, Antigravity, Cursor, Codex)
DocLayer ships with a universal agent engineering directive in [`SKILL.md`](https://github.com/paragpallavsingh/doclayer/blob/main/SKILL.md).

* **Antigravity / Gemini CLI:** Automatically discovers `SKILL.md` in repository root.
* **Claude Code / Codex:** Copy or symlink [`SKILL.md`](https://github.com/paragpallavsingh/doclayer/blob/main/SKILL.md) into your project's `.agents/skills/doclayer/SKILL.md` or system prompt rules.
* **Universal Rule:** Instruct your agent: *"Run `doclayer explain <file>` before modifying code. Follow declared AST invariants and negative runbook prohibitions."*

---

## ⚡ Performance & Scalability

Benchmarked with `scripts/benchmark_efficiency.py` across micro-benchmarks and large monorepo stress tests (500+ subsystems):

| Operation | Latency (Avg) | Latency (P95) | Throughput |
| :--- | :--- | :--- | :--- |
| **Single Layer Parse & Extract** | **0.44 ms** | **0.88 ms** | ~2,250 layers/sec |
| **Schema & Contract Validation** | **0.75 ms** | **1.65 ms** | ~1,340 validations/sec |
| **50 Subsystems Monorepo Scan** | **218 ms** | — | 229 ops/sec (85 KB RAM) |
| **500 Subsystems Large Monorepo** | **2.17 s** | — | 230 ops/sec (635 KB RAM) |
| **Git Delta Target Resolution** | **<25 ms** | — | Zero full-repo overhead |

---

## 📜 License
Distributed under the [Apache License 2.0](https://github.com/paragpallavsingh/doclayer/blob/main/LICENSE).

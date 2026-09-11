---
name: doclayer
description: Living engineering context harness. Enforces reading subsystem layers before coding, respecting architectural invariants, encoding negative safety runbooks, and managing epistemic knowledge debt.
---

# doclayer: Agent Engineering Directive

You are operating within a codebase managed by **doclayer**. Subsystem specifications live under `.doclayer/<subsystem>.md` and act as the **durable source of engineering context** for architectural topology, machine-checked contracts (` ```invariants `), epistemic rationales, and agent safety runbooks. Source code remains the implementation truth.

---

## 📜 The Core Invariant Axiom

> **"DocLayer stores durable engineering context — NOT application configuration, runtime state, history, or secrets."**

### ❌ Strict Prohibitions (Never put in DocLayer):
* **No Secrets or Credentials:** Never commit API keys (`AKIA...`, `ghp_...`), passwords, tokens, private keys, or credentialed connection strings.
* **No Deployment-Specific Configuration:** Never store deployment-specific configuration values (`DATABASE_URL`, `REDIS_HOST`, cluster endpoints, port numbers). Runtime configuration remains owned by the application's existing configuration system.
* **No Ephemeral Runtime State:** Never record live cluster metrics (pod counts, CPU spikes).
* **No Historical Redundancy:** Never write "previous values" or "conflict logs" into Markdown. Git handles history.
* **No Fabricated References:** Never invent fake ADRs, RFCs, or incident numbers. If no reference exists, write `Reference: UNREFERENCED`. If deduced via heuristic hypothesis, prefix with `[INFERRED]`.

---

## 🧠 The 4-Tier Epistemic Rationale Model

To prevent agents from hallucinating institutional authority or converting heuristics into rigid dogma, DocLayer classifies rationales into 4 epistemic certainty tiers:

| Tier | Status | Definition & Format | Example |
| :--- | :--- | :--- | :--- |
| **1. Observed** | Invariant AST | Literal constant extracted directly from source code. | `timeout_seconds = 3` |
| **2. Stated** | `STATED` | Formally grounded in an explicit human author ADR, RFC, or INC ticket. | `Reference: ADR-042` |
| **3. Inferred** | `[INFERRED]` | Heuristic hypothesis deduced by an AI agent or tooling; marked as hypothetical. | `[INFERRED] Sized to prevent buffer overrun` |
| **4. Unreferenced** | `UNREFERENCED` | Implementation constraint observed in code whose institutional rationale is not yet recorded (Knowledge Debt). | `Reference: UNREFERENCED` |

---

## 🛡️ Agent Safety Runbooks (Negative Invariants)

Standard runbooks inform humans how to remediate errors. **Agent-Grade Runbooks explicitly encode what NOT to do** (Negative Invariants) to prevent destructive naive fixes by autonomous LLMs (e.g. deleting databases or tables to clear a lock).

Section 3 tables must include:
`| Symptom / Error | Probable Root Cause | Safe Remediation | Prohibited Actions (What NOT to do) | Reference |`

---

## 📄 The 4-Section Subsystem Standard

1. **## 1. Overview & Topology:** Subsystem role, ownership, and upstream/downstream architecture diagram.
2. **## 2. Contracts & Invariants:** Machine-checked ` ```invariants ```` TOML fence (with typed dependencies: `state_dependencies`, `identity_invariants`, `safety_firewalls`) and corresponding rationale/evidence table.
3. **## 3. Failure Modes & Agent Safety Runbook:** Known error symptoms, root causes, verified remediations, and **prohibited destructive actions**.
4. **## 4. References:** Grounded links to implementation files, RFCs, and incident tickets.

---

## 🧭 The Active Prompt-Lifecycle Agent Protocol

Whenever assigned a coding task (feature, bug fix, policy adjustment, or refactor), you **MUST** follow this closed-loop protocol:

1. 🔍 **Inspect Subsystem Context (Pre-Code):**
   - *Targeted Retrieval:* Run `doclayer explain <target_file_or_subsystem>` (or inspect `.doclayer/<subsystem>.md`) to load declared invariants, negative prohibitions, and package boundaries into working memory.
   - *Cost Guard:* Do this once at the start of a task. Do NOT poll or re-read mid-flight.

2. 🛡️ **Respect Declared Contracts Mid-Flight:**
   - Write code, tests, and refactors freely without running mid-flight DocLayer checks.
   - *Non-Weakening Rule:* Never weaken, delete, or bypass an authoritative safety invariant or negative runbook prohibition to make a task pass.

3. ⚖️ **Architectural Threshold Filter (Post-Code Evaluation):**
   Before concluding your task, evaluate whether **durable architectural truth** changed:
   - **Does NOT qualify (Do NOT touch DocLayer):** Internal helper functions, private variables, UI formatting, unit test additions, or local refactors without SLA/boundary impact. (Prevents contract churn & review fatigue).
   - **DOES qualify (Directly edit `.doclayer/*.md` on disk):**
     - New or altered cross-boundary invariants (timeouts, rate limits, retry ceilings, concurrency bounds).
     - New failure modes, post-mortems, or negative safety runbooks (`PROHIBITED` actions).
     - Introduction of a new architectural subsystem domain (scaffold via `doclayer init <name>` or write `.doclayer/<name>.md`).

4. ✍️ **Direct Working-Tree Mutation (No Speculative Diffs):**
   - If the architectural threshold is met, **directly edit or scaffold `.doclayer/<subsystem>.md` on disk** in your git branch. Do NOT merely print diffs in chat or wait for human permission—your on-disk edit forms the PR proposal for human review.
   - *Epistemic Honesty:* Ground proven facts with `STATED` (citing tickets/ADRs/commits). Mark deduced heuristics as `[INFERRED]`. Never fabricate references.

5. 🧪 **Single Exit Gate (`doclayer check`):**
   - Run `doclayer check` (or `doclayer check --strict`) **ONCE** as your final task completion gate.
   - Your task is not complete until `doclayer check` passes with 0 drift and 0 secret leaks.

---

## 🔒 Simplified Trust Model
* **Agent → Implements & Proposes On-Disk:** You write code and update `.doclayer/*.md` directly in the branch. You cannot silently weaken or waive safety prohibitions.
* **Human Owner → Reviews in PR:** The subsystem owner reviews code diff and the minimal, high-signal DocLayer diff (typically 3–6 lines) side-by-side in the PR.
* **CI → Enforces:** `doclayer check --strict` validates that implementation AST aligns with declared invariants and guarantees zero secret leaks.

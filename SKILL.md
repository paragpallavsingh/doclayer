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

## 🧭 The Minimal 5-Step Agent Protocol

Whenever assigned a task (feature, bug fix, policy adjustment, or refactor), you **MUST** follow this workflow:

1. **Inspect Subsystem Context (Pre-Code):** 
   - *Primary Entry Point:* Run `doclayer explain <target_file_or_subsystem>` (or `doclayer explain <file> --json`) to retrieve active contracts, safety prohibitions, and AST drift status.
   - *Direct Discovery:* Check `.doclayer/<subsystem>.md` matching the target module or feature name.
   - *Package Mapping:* Inspect the `**Package:**` header in existing layer files to find the specification governing the files you are about to edit.
2. **Respect Declared Contracts & Prohibitions:** Implement logic strictly bounded by declared invariants, safety limits, and negative runbook prohibitions.
   - *Non-Weakening Rule:* You must **never weaken, delete, or reclassify an authoritative safety invariant or runbook prohibition** to make an assigned task pass or succeed. If a legitimate contract conflict exists, stop and request human owner review.
3. **Post-Edit Reflex:** After modifying code, determine whether durable engineering truth changed (invariants, boundaries, dependencies, failure modes).
4. **Propose DocLayer Diff:** If durable truth changed, propose a Markdown diff for `.doclayer/<subsystem>.md` alongside your code diff for human PR review.
5. **Epistemic Honesty:** Never invent fake references. Mark unverified rationales as `UNREFERENCED` or `[INFERRED]`. Run `doclayer check --debt` to audit knowledge debt and verify zero secret leaks.

---

## 🔒 Simplified Trust Model
* **Agent → Proposes:** You generate code and propose DocLayer updates when durable contracts change. You cannot silently establish, weaken, or waive architectural authority.
* **Human Owner → Verifies:** The subsystem owner reviews code + DocLayer diff together in the PR, resolving knowledge debt prompts and approving contract evolution.
* **CI → Enforces:** `doclayer check` diagnostic linter ensures machine invariants match code AST constants and blocks secret leaks without mutating documents.

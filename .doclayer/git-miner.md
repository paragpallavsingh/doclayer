# Subsystem: Git Commit History & Knowledge Miner

**Package:** `src/doclayer/git_miner.py`  
**Owner:** `@doclayer-core` (Alerts: `EP-GIT-MINER`)

---

## 1. Overview & Topology
Institutional knowledge and constant genesis miner. Queries local git repository history using zero-dependency subprocess commands (`git log -S`, `git log --grep`) to ground extracted AST symbols into commit rationales, ADRs, RFCs, and CVE references. Automatically extracts historical incident fixes and reverts into Section 3 negative safety runbooks.

```
┌─────────────────────────────────┐
│          Git Repository         │
│          (.git / commits)       │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│     git_miner (Subprocess)      │
│  (Read-Only: log, rev-parse)    │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│      Institutional Memory       │
│  (Genesis Rationale & Runbooks) │
└─────────────────────────────────┘
```

---

## 2. Contracts & Invariants

```invariants
[invariants]
git_command_timeout_seconds = 10
max_mined_commits = 50

[targets]
discovery_latency_p95_ms = 50

[dependencies]
upstream = ["doclayer-auto", "doclayer-server", "doclayer-cli"]
downstream = ["subprocess", "re", "dataclasses", "git-vcs"]
safety_invariants = [
    "never_execute_git_mutation_commands",
    "never_leak_shell_injection_vectors"
]
```

| Invariant / Contract | Why & Rationale | Reference | Evidence Anchor |
| :--- | :--- | :--- | :--- |
| `git_command_timeout_seconds = 10` | Caps git subprocess execution to prevent hanging on corrupted repos or locks | `SEC-DIRECTIVE` | `src/doclayer/git_miner.py::GIT_COMMAND_TIMEOUT_SECONDS` |
| `max_mined_commits = 50` | Bound log traversal depth to maintain fast synthesis under 100ms | `PERF-TARGET` | `src/doclayer/git_miner.py::MAX_MINED_COMMITS` |

---

## 3. Failure Modes & Agent Safety Runbook

| Symptom / Error | Probable Root Cause | Safe Remediation | Prohibited Actions (What NOT to do) | Reference |
| :--- | :--- | :--- | :--- | :--- |
| `ERR_GIT_TIMEOUT` | Git process hung on index lock or huge history | Abort command after timeout and fall back to shallow heuristics | NEVER increase subprocess timeout indefinitely without bounds | `SEC-DIRECTIVE` |
| `ERR_GIT_MUTATION` | Miner routine attempting state change | Restrict subprocess strictly to read-only commands (`log`, `rev-parse`) | NEVER run mutating git commands (commit, push, reset, checkout) inside discovery or miner routines | `SEC-DIRECTIVE` |
| `ERR_NOT_GIT_REPO` | Directory lacks `.git` or is untracked | Verify repository root using `is_git_repo` before executing queries | NEVER assume working directory is always a git repository | `AUTHOR-DIRECTIVE` |

---

## 4. References
* Implementation: `src/doclayer/git_miner.py`
* Git log specification: `SPEC-GIT-MINING`

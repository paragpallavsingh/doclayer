# Subsystem: {{SUBSYSTEM_TITLE}}

**Package:** `{{PACKAGE_PATH}}`  
**Owner:** `{{OWNER_TEAM}}` (Alerts: `{{ALERT_CHANNEL}}`)

---

## 1. Overview & Topology
{{OVERVIEW_DESCRIPTION}}

```
{{CALL_FLOW_DIAGRAM}}
```

---

## 2. Contracts & Invariants

```invariants
{{INVARIANTS_BLOCK}}
```

| Invariant / Contract | Why & Rationale | Reference | Evidence Anchor |
| :--- | :--- | :--- | :--- |
{{INVARIANTS_TABLE}}

### Core Execution Pipelines & Data Transformations

| Pipeline / Function | Trigger / Inputs | Core Transformation / Business Logic | Output / State Change | Evidence Anchor |
| :--- | :--- | :--- | :--- | :--- |
{{PIPELINES_TABLE}}

---

## 3. Failure Modes & Agent Safety Runbook

| Symptom / Error | Probable Root Cause | Safe Remediation | Prohibited Actions (What NOT to do) | Reference |
| :--- | :--- | :--- | :--- | :--- |
{{RUNBOOK_TABLE}}

---

## 4. References
{{REFERENCES_BLOCK}}

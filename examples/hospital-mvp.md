# Subsystem: Hospital Emergency & EHR Care Delivery Platform

**Package:** `src/hospital_mvp/`  
**Owner:** `@clinical-platform` (Alerts: `EP-HOSPITAL-CARE-TIER1`)

---

## 1. Overview & Topology
Monolithic 5-module clinical care and Electronic Health Record (EHR) emergency platform. Coordinates clinician access, patient registries, emergency triage queues, vital sign telemetry, and immutable audit logs.

```
                   [Ambulance / Web Client]
                              │
                              ▼
                   ┌───────────────────────┐
                   │  1. auth_audit.py     │ <── (Clinician RBAC & HIPAA Audit)
                   └──────────┬────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│2. triage_engine  │ │3. patient_reg    │ │4. vitals_telemetry│
│   (ESI 1-5 Queue)│ │   (AES-256 EHR)  │ │   (HL7/FHIR Stream│
└────────┬─────────┘ └────────┬─────────┘ └────────┬─────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              ▼
                   ┌───────────────────────┐
                   │  5. billing_claims.py │
                   │     (Insurance API)   │
                   └───────────────────────┘
```

### Module Layout (5-File Architecture)
1. `src/hospital_mvp/auth_audit.py`: Clinician session auth & statutory audit log.
2. `src/hospital_mvp/patient_registry.py`: Patient demographic registry with AES-256 field-level encryption.
3. `src/hospital_mvp/triage_engine.py`: Emergency Severity Index (ESI) triage scoring & queue priority.
4. `src/hospital_mvp/vitals_telemetry.py`: Real-time bedside vitals monitor & HL7/FHIR ingest.
5. `src/hospital_mvp/billing_claims.py`: Insurance pre-authorization & billing claims dispatcher.

---

## 2. Contracts & Invariants

```invariants
[invariants]
emergency_triage_sla_seconds = 10
phi_encryption_cipher = "AES-256-GCM"
audit_retention_years = 7
max_vitals_telemetry_lag_seconds = 2

[targets]
triage_dispatch_p99_ms = 50

[dependencies]
upstream = ["ambulance-dispatch", "nurse-station-ui", "bedside-monitors"]
downstream = ["hl7-fhir-gateway", "insurance-clearinghouse", "pagerduty-clinical"]
state_dependencies = ["patient_ehr_store", "triage_priority_queue", "audit_trail_wal"]
identity_invariants = ["medical_record_number_immutable", "clinician_npi_unique"]
safety_firewalls = [
    "never_expose_unmasked_phi",
    "never_delete_medical_records",
    "never_bypass_clinical_audit_trail"
]
```

| Invariant / Contract | Why & Rationale | Reference | Evidence Anchor |
| :--- | :--- | :--- | :--- |
| `emergency_triage_sla_seconds = 10` | ESI-1 Level critical cardiac/stroke triage response threshold | `AHA-GUIDELINE-2024` | `src/hospital_mvp/triage_engine.py` |
| `phi_encryption_cipher = "AES-256-GCM"` | Statutory requirement for Protected Health Information at rest | `HIPAA-164.312` | `src/hospital_mvp/patient_registry.py` |
| `audit_retention_years = 7` | Statutory medical malpractice and regulatory retention mandate | `DISHA-SEC-04` | `src/hospital_mvp/auth_audit.py` |
| `max_vitals_telemetry_lag_seconds = 2` | Critical alert broadcast latency ceiling for ICU telemetry | `HL7-FHIR-R4` | `src/hospital_mvp/vitals_telemetry.py` |

---

## 3. Failure Modes & Agent Safety Runbook

| Symptom / Error | Probable Root Cause | Safe Remediation | Prohibited Actions (What NOT to do) | Reference |
| :--- | :--- | :--- | :--- | :--- |
| `ERR_PHI_EXPOSED` | Unsanitized logging of patient name or SSN in application logs | Rotate logging keys; trigger emergency data incident response | NEVER output unmasked patient data in LLM prompts, CLI outputs, or debug logs | `HIPAA-164.312` |
| `ERR_TRIAGE_STARVATION` | Low-priority ESI-4/5 patients blocking emergency ESI-1 triage slots | Trigger dynamic priority escalation and alert on-call charge nurse | NEVER drop or cancel unassigned emergency patients from queue to clear backpressure | `AHA-GUIDELINE-2024` |
| `ERR_AUDIT_DISK_FULL` | Write-Ahead Log (WAL) audit disk threshold exceeded | Route audit events to emergency S3 bucket backup | NEVER disable or bypass audit logging under high load (zero audit loss tolerated) | `DISHA-SEC-04` |

---

## 4. References
* Implementation: `src/hospital_mvp/`
* Statutory Regulations: `HIPAA-164.312` (Security Rule), `DISHA-SEC-04` (Health Data Privacy)
* Clinical Standards: `HL7-FHIR-R4`, `AHA-GUIDELINE-2024`

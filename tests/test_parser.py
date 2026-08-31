import tempfile
import unittest
from pathlib import Path
from doclayer.parser import (
    extract_invariants_fence,
    parse_invariants_toml,
    parse_markdown_table,
    parse_layer_file,
    classify_epistemic_status,
    extract_contracts_from_section,
    extract_runbook_from_section,
    extract_semantic_dependencies,
)


class TestDoclayerParser(unittest.TestCase):
    def test_extract_invariants_fence(self):
        sample = """
# Test Subsystem
## 2. Contracts & Invariants
```invariants
[invariants]
timeout_ms = 1500
max_network_retries = 2
```
"""
        fence = extract_invariants_fence(sample)
        self.assertIsNotNone(fence)
        self.assertIn("timeout_ms = 1500", fence)

    def test_parse_invariants_toml(self):
        toml_content = """
[invariants]
timeout_ms = 1500
allowed_currencies = ["USD", "EUR"]

[dependencies]
upstream = ["gateway"]
downstream = ["stripe"]
state_dependencies = ["redis_session"]
identity_invariants = ["idempotency_key_unique"]
safety_firewalls = ["never_store_cvv"]
"""
        data, err = parse_invariants_toml(toml_content)
        self.assertIsNone(err)
        self.assertIsNotNone(data)
        self.assertEqual(data["invariants"]["timeout_ms"], 1500)
        self.assertEqual(data["invariants"]["allowed_currencies"], ["USD", "EUR"])

        deps = extract_semantic_dependencies(data)
        self.assertEqual(deps.upstream, ["gateway"])
        self.assertEqual(deps.downstream, ["stripe"])
        self.assertEqual(deps.state_dependencies, ["redis_session"])
        self.assertEqual(deps.identity_invariants, ["idempotency_key_unique"])
        self.assertEqual(deps.safety_firewalls, ["never_store_cvv"])

    def test_classify_epistemic_status(self):
        # Stated references
        self.assertEqual(classify_epistemic_status("SLA budget", "RFC-204"), "STATED")
        self.assertEqual(classify_epistemic_status("Safety rule", "ADR-041"), "STATED")
        self.assertEqual(classify_epistemic_status("Incident response", "INC-3301"), "STATED")
        self.assertEqual(classify_epistemic_status("Healthcare regulation", "DISHA-SEC-01"), "STATED")

        # Inferred heuristics
        self.assertEqual(classify_epistemic_status("[INFERRED] Heuristic for stability", "UNREFERENCED"), "INFERRED")
        self.assertEqual(classify_epistemic_status("Deduced by agent", "[INFERRED]"), "INFERRED")

        # Unreferenced knowledge debt
        self.assertEqual(classify_epistemic_status("Unknown threshold", "UNREFERENCED"), "UNREFERENCED")
        self.assertEqual(classify_epistemic_status("Empirical value", "UNKNOWN"), "UNREFERENCED")
        self.assertEqual(classify_epistemic_status("No reference", "`UNREFERENCED`"), "UNREFERENCED")

    def test_parse_subsystem_layer_file_with_safety_and_epistemic(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "order-router.md"
            file_path.write_text("""# Subsystem: Order Router Service

**Package:** `src/orders.py`
**Owner:** `@order-core` (Alerts: `EP-ORDERS`)

## 1. Overview & Topology
Handles customer order lifecycle.

## 2. Contracts & Invariants
```invariants
[invariants]
timeout_seconds = 3
max_retries = 2
slug_primary_key = true

[dependencies]
upstream = ["api-gateway"]
downstream = ["payment-service"]
state_dependencies = ["order_db_state"]
identity_invariants = ["slug_primary_key"]
safety_firewalls = ["never_delete_orders"]
```
| Invariant / Contract | Why & Rationale | Reference | Evidence Anchor |
| :--- | :--- | :--- | :--- |
| `timeout_seconds = 3` | SLA budget | `ADR-001` | `src/orders.py::TIMEOUT` |
| `max_retries = 2` | [INFERRED] Prevent retry storm | `UNREFERENCED` | `src/orders.py::MAX_RETRIES` |
| `slug_primary_key = true` | Universal identity model | `UNREFERENCED` | `src/orders.py::SLUG` |

## 3. Failure Modes & Agent Safety Runbook
| Symptom / Error | Probable Root Cause | Safe Remediation | Prohibited Actions (What NOT to do) | Reference |
| :--- | :--- | :--- | :--- | :--- |
| `ERR_DB_LOCKED` | SQLite lock | Retry with 500ms backoff | NEVER delete or drop database to clear lock | `INC-109` |

## 4. References
* Implementation: `src/orders.py`
""", encoding="utf-8")
            doc = parse_layer_file(file_path)
            self.assertEqual(doc.title, "Order Router Service")
            self.assertEqual(doc.package, "src/orders.py")
            self.assertEqual(len(doc.contracts), 3)

            # Contract 1: STATED
            self.assertEqual(doc.contracts[0].epistemic_status, "STATED")
            # Contract 2: INFERRED
            self.assertEqual(doc.contracts[1].epistemic_status, "INFERRED")
            # Contract 3: UNREFERENCED
            self.assertEqual(doc.contracts[2].epistemic_status, "UNREFERENCED")

            # Runbook Negative Invariant
            self.assertEqual(len(doc.runbook_items), 1)
            self.assertIn("NEVER delete or drop database", doc.runbook_items[0].prohibited_actions)

            # Semantic dependencies
            self.assertEqual(doc.semantic_deps.safety_firewalls, ["never_delete_orders"])
            self.assertEqual(doc.semantic_deps.state_dependencies, ["order_db_state"])


if __name__ == "__main__":
    unittest.main()

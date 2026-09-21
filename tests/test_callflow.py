import ast
from pathlib import Path
import tempfile
import unittest

from doclayer.callflow import (
    analyze_python_files,
    analyze_polyglot_files,
    PipelineContract,
)
from doclayer.parser import parse_layer_file, extract_pipelines_from_section
from doclayer.validator import validate_file


class TestCallFlowAndPipelines(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_python_callflow_and_pipeline_extraction(self):
        src_dir = self.tmp_path / "src" / "tracker"
        src_dir.mkdir(parents=True)

        server_file = src_dir / "server.py"
        server_file.write_text("""
def handle_trade(owner: str, symbol: str, qty: float, price: float):
    \"\"\"Execute closed-loop trade and update balance sheet.\"\"\"
    import sqlite3
    conn = sqlite3.connect("portfolio.db")
    total = round(qty * price, 2)
    conn.execute("INSERT INTO trades VALUES (?, ?, ?)", (owner, symbol, total))
    conn.commit()
    return {"status": "ok", "total": total}

def calculate_rebalance(holdings: list, target_weights: dict) -> dict:
    \"\"\"Compute target asset allocation delta.\"\"\"
    diffs = {}
    for h in holdings:
        diffs[h] = 0.5
    return diffs
""", encoding="utf-8")

        summary = analyze_python_files([server_file], repo_root=self.tmp_path)
        self.assertTrue(len(summary.pipelines) >= 2)
        self.assertIn("server.py (Entrypoint)", summary.entry_points)
        self.assertIn("server.py", summary.ascii_diagram)

        # Check handle_trade pipeline
        trade_pipe = next((p for p in summary.pipelines if "handle_trade" in p.function_name), None)
        self.assertIsNotNone(trade_pipe)
        self.assertIn("owner", trade_pipe.inputs)
        self.assertIn("Execute closed-loop trade", trade_pipe.transformation)
        self.assertIn("Persists database state", trade_pipe.output_state)
        self.assertIn("src/tracker/server.py::handle_trade", trade_pipe.evidence_anchor)

        # Check calculate_rebalance pipeline
        reb_pipe = next((p for p in summary.pipelines if "calculate_rebalance" in p.function_name), None)
        self.assertIsNotNone(reb_pipe)
        self.assertIn("Compute target asset allocation delta", reb_pipe.transformation)

    def test_polyglot_ts_go_extraction(self):
        src_dir = self.tmp_path / "src" / "billing"
        src_dir.mkdir(parents=True)

        ts_file = src_dir / "handler.ts"
        ts_file.write_text("""
export async function processInvoice(invoiceId: string, amount: number) {
    return { paid: true };
}
""", encoding="utf-8")

        summary = analyze_polyglot_files([ts_file], repo_root=self.tmp_path)
        self.assertTrue(len(summary.pipelines) >= 1)
        inv_pipe = summary.pipelines[0]
        self.assertIn("processInvoice", inv_pipe.function_name)
        self.assertIn("invoiceId", inv_pipe.inputs)

    def test_pipeline_parsing_and_validation(self):
        doc_file = self.tmp_path / "subsystem.md"
        doc_file.write_text("""# Subsystem: Rebalance Engine

**Package:** `src/engine/`
**Owner:** `@quant-team`

---

## 1. Overview & Topology
Handles automated asset allocation rebalancing.

```
[UI Router] --> [Rebalance Engine] --> [SQLite DB]
```

---

## 2. Contracts & Invariants

```invariants
[invariants]
target_equity_pct = 0.55
```

| Invariant / Contract | Why & Rationale | Reference | Evidence Anchor |
| :--- | :--- | :--- | :--- |
| `target_equity_pct = 0.55` | Core equity allocation ceiling | `IPS-2026` | `src/engine/config.py::TARGET_EQUITY` |

### Core Execution Pipelines & Data Transformations

| Pipeline / Function | Trigger / Inputs | Core Transformation / Business Logic | Output / State Change | Evidence Anchor |
| :--- | :--- | :--- | :--- | :--- |
| `rebalance_portfolio()` | `(holdings: list, cash: float)` | Computes allocation gap and allocates capital into lagging buckets | Returns deployment orders | `src/engine/rebalance.py::rebalance_portfolio` |

---

## 3. Failure Modes & Agent Safety Runbook

| Symptom / Error | Probable Root Cause | Safe Remediation | Prohibited Actions (What NOT to do) | Reference |
| :--- | :--- | :--- | :--- | :--- |
| `ERR_OVERALLOCATION` | Target weights exceed 1.0 | Normalize bucket ratios to 100% | NEVER force trade execution when sum != 1.0 | `INC-REB-01` |

---

## 4. References
* Engine: `src/engine/`
""", encoding="utf-8")

        doc = parse_layer_file(doc_file)
        self.assertEqual(len(doc.pipelines), 1)
        self.assertEqual(doc.pipelines[0].function_name, "`rebalance_portfolio()`")
        self.assertIn("Computes allocation gap", doc.pipelines[0].transformation)

        report = validate_file(doc_file, check_drift=False)
        self.assertTrue(report.is_valid)
        self.assertEqual(len(report.pipelines), 1)


if __name__ == "__main__":
    unittest.main()

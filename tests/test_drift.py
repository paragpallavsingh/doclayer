import tempfile
import unittest
from pathlib import Path
from doclayer.drift import detect_invariant_drift, extract_constants_from_python_file
from doclayer.validator import validate_file


class TestDoclayerDriftDetection(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_extract_constants(self):
        py_file = self.tmp_path / "sample.py"
        py_file.write_text(
            "MAX_TIMEOUT_SECONDS = 3\nMINIMUM_USER_ID = 10001\nALLOWED_MODES = ['A', 'B']\n",
            encoding="utf-8"
        )
        constants = extract_constants_from_python_file(py_file)
        self.assertIn("max_timeout_seconds", constants)
        self.assertIn("timeout_seconds", constants)
        self.assertEqual(constants["timeout_seconds"][0], 3)
        self.assertEqual(constants["minimum_user_id"][0], 10001)

    def test_detect_no_drift_when_matching(self):
        py_file = self.tmp_path / "service.py"
        py_file.write_text("MAX_WEBHOOK_TIMEOUT_SECONDS = 3\nMINIMUM_RUN_AS_USER = 10001\n", encoding="utf-8")
        
        invariants = {
            "runtime": {
                "webhook_timeout_seconds": 3,
                "minimum_run_as_user": 10001,
            }
        }
        drifts = detect_invariant_drift(invariants, [py_file])
        self.assertEqual(len(drifts), 0)

    def test_detect_drift_when_code_diverges(self):
        py_file = self.tmp_path / "service.py"
        py_file.write_text("MAX_WEBHOOK_TIMEOUT_SECONDS = 5\nMINIMUM_RUN_AS_USER = 10001\n", encoding="utf-8")
        
        invariants = {
            "runtime": {
                "webhook_timeout_seconds": 3,  # DocLayer says 3, code changed to 5
                "minimum_run_as_user": 10001,
            }
        }
        drifts = detect_invariant_drift(invariants, [py_file])
        self.assertEqual(len(drifts), 1)
        self.assertEqual(drifts[0].invariant_key, "webhook_timeout_seconds")
        self.assertEqual(drifts[0].doc_value, 3)
        self.assertEqual(drifts[0].code_value, 5)
        self.assertEqual(drifts[0].symbol_name, "MAX_WEBHOOK_TIMEOUT_SECONDS")

    def test_polyglot_typescript_drift(self):
        ts_file = self.tmp_path / "service.ts"
        ts_file.write_text("export const MAX_CONNECTIONS = 50;\nexport const TIMEOUT_MS = 3000;\n", encoding="utf-8")

        invariants = {
            "invariants": {
                "max_connections": 50,
                "timeout_ms": 5000,  # Doc says 5000, TS code is 3000 -> drift!
            }
        }
        drifts = detect_invariant_drift(invariants, [ts_file])
        self.assertEqual(len(drifts), 1)
        self.assertEqual(drifts[0].symbol_name, "TIMEOUT_MS")
        self.assertEqual(drifts[0].doc_value, 5000)
        self.assertEqual(drifts[0].code_value, 3000)

    def test_polyglot_go_drift(self):
        go_file = self.tmp_path / "pool.go"
        go_file.write_text("""package pool

const (
    MaxWorkers = 20
    QueueCapacity = 100
)
const DefaultTimeout = 30
""", encoding="utf-8")

        invariants = {
            "invariants": {
                "max_workers": 20,
                "queue_capacity": 100,
                "default_timeout": 30,
            }
        }
        drifts = detect_invariant_drift(invariants, [go_file])
        self.assertEqual(len(drifts), 0)

        # Divergent invariant
        invariants["invariants"]["max_workers"] = 50
        drifts = detect_invariant_drift(invariants, [go_file])
        self.assertEqual(len(drifts), 1)
        self.assertEqual(drifts[0].symbol_name, "MaxWorkers")
        self.assertEqual(drifts[0].code_value, 20)
        self.assertEqual(drifts[0].doc_value, 50)

    def test_polyglot_rust_drift(self):
        rs_file = self.tmp_path / "config.rs"
        rs_file.write_text("""
pub const MAX_RETRIES: u32 = 3;
pub const BUFFER_SIZE: usize = 1024_usize;
const TIMEOUT_SECS: u64 = 60;
""", encoding="utf-8")

        invariants = {
            "invariants": {
                "max_retries": 3,
                "buffer_size": 1024,
                "timeout_secs": 60,
            }
        }
        drifts = detect_invariant_drift(invariants, [rs_file])
        self.assertEqual(len(drifts), 0)

        # Divergent invariant
        invariants["invariants"]["buffer_size"] = 2048
        drifts = detect_invariant_drift(invariants, [rs_file])
        self.assertEqual(len(drifts), 1)
        self.assertEqual(drifts[0].symbol_name, "BUFFER_SIZE")
        self.assertEqual(drifts[0].code_value, 1024)
        self.assertEqual(drifts[0].doc_value, 2048)

    def test_warns_on_unsupported_package(self):
        cpp_file = self.tmp_path / "service.cpp"
        cpp_file.write_text("int timeout = 5;\n", encoding="utf-8")

        layer_file = self.tmp_path / "service.md"
        layer_file.write_text(f"""# Subsystem: CPP Service
**Package:** `{cpp_file.as_posix()}`
**Owner:** `@systems`

## 1. Overview
CPP Service.

## 2. Contracts & Invariants
```invariants
[invariants]
timeout_seconds = 5
```
| Invariant | Why | Reference | Evidence Anchor |
| :--- | :--- | :--- | :--- |
| `timeout_seconds = 5` | SLA | `RFC-1` | `{cpp_file.as_posix()}` |

## 3. Failure Modes & Runbook
| Symptom | Cause | Safe Remediation | Prohibited Actions | Reference |
| :--- | :--- | :--- | :--- | :--- |
| `ERR` | Lag | Retry | None | `INC-1` |

## 4. References
* Ref: `RFC-1`
""", encoding="utf-8")

        report = validate_file(layer_file)
        self.assertTrue(report.is_valid)
        self.assertTrue(any("non-supported source files" in w for w in report.warnings))


if __name__ == "__main__":
    unittest.main()

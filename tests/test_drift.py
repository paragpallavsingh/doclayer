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

    def test_warns_on_non_python_package(self):
        ts_file = self.tmp_path / "service.ts"
        ts_file.write_text("export const TIMEOUT = 5;\n", encoding="utf-8")

        layer_file = self.tmp_path / "service.md"
        layer_file.write_text(f"""# Subsystem: TS Service
**Package:** `{ts_file.as_posix()}`
**Owner:** `@frontend`

## 1. Overview
TS Service.

## 2. Contracts & Invariants
```invariants
[invariants]
timeout_seconds = 5
```
| Invariant | Why | Reference | Evidence Anchor |
| :--- | :--- | :--- | :--- |
| `timeout_seconds = 5` | SLA | `RFC-1` | `{ts_file.as_posix()}` |

## 3. Failure Modes & Runbook
| Symptom | Cause | Safe Remediation | Prohibited Actions | Reference |
| :--- | :--- | :--- | :--- | :--- |
| `ERR` | Lag | Retry | None | `INC-1` |

## 4. References
* Ref: `RFC-1`
""", encoding="utf-8")

        report = validate_file(layer_file)
        self.assertTrue(report.is_valid)
        self.assertTrue(any("non-Python source files" in w for w in report.warnings))


if __name__ == "__main__":
    unittest.main()

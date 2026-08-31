import argparse
import json
import io
import sys
import tempfile
import unittest
from pathlib import Path
from doclayer.cli import cmd_explain, find_layer_for_target


class TestDoclayerExplain(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.layers_dir = Path(self.temp_dir.name) / ".doclayer"
        self.layers_dir.mkdir(parents=True, exist_ok=True)

        self.src_file = Path(self.temp_dir.name) / "janitor.py"
        self.src_file.write_text("MAX_BATCH = 200\n", encoding="utf-8")

        self.layer_file = self.layers_dir / "kube-janitor.md"
        self.layer_file.write_text(f"""# Subsystem: K8s Janitor
**Package:** `{self.src_file.as_posix()}`
**Owner:** `@platform-infra`

## 1. Overview
Scans namespaces.

## 2. Contracts & Invariants
```invariants
[invariants]
max_batch = 200
```
| Invariant / Contract | Why & Rationale | Reference | Evidence Anchor |
| :--- | :--- | :--- | :--- |
| `max_batch = 200` | Prevent etcd bottleneck | `RFC-204` | `{self.src_file.as_posix()}` |

## 3. Failure Modes & Runbook
| Symptom / Error | Probable Cause | Safe Remediation | Prohibited Actions (What NOT to do) | Reference |
| :--- | :--- | :--- | :--- | :--- |
| `ERR_THROTTLED` | API rate limit | Backoff | NEVER bypass rate limiting | `RFC-204` |

## 4. References
* RFC: `RFC-204`
""", encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_find_layer_by_slug(self):
        found = find_layer_for_target("kube-janitor", layers_dir=self.layers_dir)
        self.assertIsNotNone(found)
        self.assertEqual(found.name, "kube-janitor.md")

    def test_find_layer_by_source_path(self):
        found = find_layer_for_target(self.src_file.as_posix(), layers_dir=self.layers_dir)
        self.assertIsNotNone(found)
        self.assertEqual(found.name, "kube-janitor.md")

    def test_cmd_explain_human_output(self):
        args = argparse.Namespace(target="kube-janitor", path=str(self.layers_dir), json=False)
        rc = cmd_explain(args)
        self.assertEqual(rc, 0)

    def test_cmd_explain_json_output(self):
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            args = argparse.Namespace(target="kube-janitor", path=str(self.layers_dir), json=True)
            rc = cmd_explain(args)
            self.assertEqual(rc, 0)
            output = sys.stdout.getvalue()
            data = json.loads(output)
            self.assertEqual(data["subsystem"], "K8s Janitor")
            self.assertEqual(len(data["contracts"]), 1)
            self.assertEqual(data["contracts"][0]["reference"], "`RFC-204`")
            self.assertIn("NEVER bypass rate limiting", data["safety_prohibitions"][0]["prohibited_actions"])
        finally:
            sys.stdout = old_stdout

    def test_cmd_explain_nonexistent_returns_nonzero(self):
        args = argparse.Namespace(target="nonexistent-system", path=str(self.layers_dir), json=False)
        rc = cmd_explain(args)
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()

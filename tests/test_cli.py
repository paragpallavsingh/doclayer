import argparse
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from doclayer.cli import cmd_init, cmd_check, cmd_rca, cmd_inspect, main
from doclayer.validator import validate_file


class TestDoclayerCLI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.layers_dir = Path(self.temp_dir.name) / ".doclayer"
        self.layers_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_init_creates_layer(self):
        args = argparse.Namespace(
            subsystem="billing-worker",
            dir=str(self.layers_dir),
            title="Billing Worker Pipeline",
            package="src/modules/billing/",
            owner="@billing-core",
            alert="EP-BILLING-ALERTS",
            force=False,
        )
        rc = cmd_init(args)
        self.assertEqual(rc, 0)
        target_file = self.layers_dir / "billing-worker.md"
        self.assertTrue(target_file.exists())

        # Check validation
        report = validate_file(target_file)
        self.assertTrue(report.is_valid, f"Validation errors: {report.errors}")
        self.assertEqual(report.title, "Billing Worker Pipeline")

    def test_init_bare_existing_workspace(self):
        # Create dummy layers
        (self.layers_dir / "analyzer.md").write_text("# Analyzer\n", encoding="utf-8")
        (self.layers_dir / "core.md").write_text("# Core\n", encoding="utf-8")
        (self.layers_dir / "screener.md").write_text("# Screener\n", encoding="utf-8")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            args = argparse.Namespace(
                subsystem=None,
                dir=str(self.layers_dir),
                force=False,
            )
            rc = cmd_init(args)
        self.assertEqual(rc, 0)
        output = buf.getvalue()
        self.assertIn("[OK] doclayer already initialized in", output)
        self.assertIn("3 layers found", output)
        self.assertIn("analyzer.md", output)
        self.assertIn("core.md", output)
        self.assertIn("screener.md", output)
        self.assertIn("Run 'doclayer check'", output)
        self.assertIn("Run 'doclayer explain <file>'", output)
        self.assertIn("Run 'doclayer init <name>'", output)

    def test_init_bare_new_workspace(self):
        new_dir = Path(self.temp_dir.name) / "new_repo" / ".doclayer"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            args = argparse.Namespace(
                subsystem=None,
                dir=str(new_dir),
                force=False,
            )
            rc = cmd_init(args)
        self.assertEqual(rc, 0)
        self.assertTrue(new_dir.exists())
        output = buf.getvalue()
        self.assertIn("[OK] Initialized empty doclayer workspace in", output)
        self.assertIn("Run 'doclayer init <name>'", output)

    def test_init_cli_bare_parser(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main(["init", "--dir", str(self.layers_dir)])
        self.assertEqual(rc, 0)

    def test_check_with_debt_audit(self):
        init_args = argparse.Namespace(
            subsystem="auth-engine",
            dir=str(self.layers_dir),
            title="Authentication & Session Routing",
            package="src/auth.py",
            owner="@security-team",
            alert="EP-AUTH",
            force=False,
        )
        self.assertEqual(cmd_init(init_args), 0)
        doc_path = self.layers_dir / "auth-engine.md"

        args = argparse.Namespace(path=str(doc_path), debt=True, strict=False)
        rc = cmd_check(args)
        self.assertEqual(rc, 0)

    def test_check_strict_mode_fails_on_drift(self):
        # Create a Python file with diverging constant
        src_file = Path(self.temp_dir.name) / "service.py"
        src_file.write_text("TIMEOUT_SECONDS = 10\n", encoding="utf-8")

        layer_file = self.layers_dir / "service.md"
        layer_file.write_text(f"""# Subsystem: Service
**Package:** `{src_file.as_posix()}`
**Owner:** `@team`

## 1. Overview
Service overview.

## 2. Contracts & Invariants
```invariants
[invariants]
timeout_seconds = 3
```
| Invariant / Contract | Why & Rationale | Reference | Evidence Anchor |
| :--- | :--- | :--- | :--- |
| `timeout_seconds = 3` | SLA | `RFC-1` | `{src_file.as_posix()}` |

## 3. Failure Modes & Runbook
| Symptom | Cause | Safe Remediation | Prohibited Actions | Reference |
| :--- | :--- | :--- | :--- | :--- |
| `ERR` | Downstream | Retry | Do not kill | `INC-1` |

## 4. References
* Ref: `RFC-1`
""", encoding="utf-8")

        # Standard check passes with warning
        args_normal = argparse.Namespace(path=str(layer_file), debt=False, strict=False)
        self.assertEqual(cmd_check(args_normal), 0)

        # Strict check fails with exit code 1
        args_strict = argparse.Namespace(path=str(layer_file), debt=False, strict=True)
        self.assertEqual(cmd_check(args_strict), 1)

    def test_inspect_subsystem(self):
        init_args = argparse.Namespace(
            subsystem="auth-engine",
            dir=str(self.layers_dir),
            title="Authentication & Session Routing",
            package="src/auth.py",
            owner="@security-team",
            alert="EP-AUTH",
            force=False,
        )
        self.assertEqual(cmd_init(init_args), 0)

        inspect_args = argparse.Namespace(subsystem="auth-engine", path=str(self.layers_dir))
        rc = cmd_inspect(inspect_args)
        self.assertEqual(rc, 0)

    def test_rca_injects_decision_and_negative_invariant(self):
        init_args = argparse.Namespace(
            subsystem="order-service",
            dir=str(self.layers_dir),
            title="Order Processing Service",
            package="src/modules/orders/",
            owner="@order-team",
            alert="EP-ORDERS",
            force=False,
        )
        self.assertEqual(cmd_init(init_args), 0)

        # Inject RCA with negative invariant (prohibited action)
        rca_args = argparse.Namespace(
            subsystem="order-service",
            path=str(self.layers_dir),
            incident="INC-9912",
            decision="Enforce max 5s lock wait",
            rationale="Prevent PostgreSQL connection pool exhaustion",
            invariant="invariants.timeout_seconds = 5",
            symptom="ERR_POOL_EXHAUSTION",
            remediation="Drain idle DB pool connections",
            prohibited="NEVER kill active transactions without master node approval",
            anchor="src/modules/orders/pool.py",
        )
        rc = cmd_rca(rca_args)
        self.assertEqual(rc, 0)

        # Check file content
        target_file = self.layers_dir / "order-service.md"
        content = target_file.read_text(encoding="utf-8")
        self.assertIn("INC-9912", content)
        self.assertIn("Enforce max 5s lock wait", content)
        self.assertIn("ERR_POOL_EXHAUSTION", content)
        self.assertIn("timeout_seconds = 5", content)
        self.assertIn("NEVER kill active transactions", content)

        # Re-validate
        report = validate_file(target_file)
        self.assertTrue(report.is_valid, f"Validation errors: {report.errors}")
        self.assertGreaterEqual(report.negative_invariants_count, 1)

    def test_resolve_layers_for_changed_files(self):
        from doclayer.cli import resolve_layers_for_changed_files
        payment_file = self.layers_dir / "payment.md"
        payment_file.write_text(
            "# Subsystem: Payments\n\n**Package:** `src/modules/payments/`\n**Owner:** `@billing`\n\n## 1. Overview & Topology\n\n## 2. Contracts & Invariants\n```invariants\n[invariants]\ntimeout_ms = 1500\n```\n\n## 3. Failure Modes & Runbook\n\n## 4. References\n",
            encoding="utf-8"
        )
        
        # Test 1: Direct layer edit
        matched = resolve_layers_for_changed_files(self.layers_dir, [".doclayer/payment.md"])
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0].name, "payment.md")

        # Test 2: Source file edit matching declared package
        matched = resolve_layers_for_changed_files(self.layers_dir, ["src/modules/payments/adapters/stripe.py"])
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0].name, "payment.md")

        # Test 3: Unrelated file
        matched = resolve_layers_for_changed_files(self.layers_dir, ["src/modules/unrelated/foo.py"])
        self.assertEqual(len(matched), 0)


if __name__ == "__main__":
    unittest.main()

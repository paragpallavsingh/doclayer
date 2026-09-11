import subprocess
import tempfile
import unittest
from pathlib import Path

from doclayer.auto import synthesize_repo_layers
from doclayer.validator import validate_file


class TestDoclayerAuto(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_auto_synthesis_polyglot_repo(self):
        repo = self.tmp_path / "polyglot-repo"
        repo.mkdir()

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=str(repo), capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Auto Tester"], cwd=str(repo), capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "auto@doclayer.dev"], cwd=str(repo), capture_output=True, check=True)

        # 1. Create a TypeScript service
        ts_dir = repo / "src" / "gateway"
        ts_dir.mkdir(parents=True)
        (ts_dir / "server.ts").write_text("""
export const MAX_CONCURRENT_REQUESTS = 500;
export const TIMEOUT_MS = 2500;
""", encoding="utf-8")

        # 2. Create a Go service
        go_dir = repo / "src" / "billing"
        go_dir.mkdir(parents=True)
        (go_dir / "worker.go").write_text("""package billing
const (
    MaxBatchSize = 100
    WorkerConcurrency = 8
)
""", encoding="utf-8")

        # Commit files
        subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "feat: initialize gateway and billing services\n\nWhy: configure production limits per RFC-880"],
            cwd=str(repo),
            capture_output=True,
            check=True
        )

        # Run auto synthesis
        output_dir = repo / ".doclayer"
        results = synthesize_repo_layers(repo_path=repo, output_dir=output_dir, force=True)

        self.assertEqual(len(results), 2)
        gateway_res = next(r for r in results if r.subsystem_slug == "gateway")
        billing_res = next(r for r in results if r.subsystem_slug == "billing")

        self.assertTrue(gateway_res.created)
        self.assertTrue(billing_res.created)
        self.assertTrue(gateway_res.target_file.exists())
        self.assertTrue(billing_res.target_file.exists())

        # Validate the generated files pass doclayer validation and have zero drift
        gw_report = validate_file(gateway_res.target_file, check_drift=True)
        self.assertTrue(gw_report.is_valid)
        self.assertEqual(len(gw_report.drifts), 0)
        self.assertGreater(gw_report.total_contracts_count, 0)

        bill_report = validate_file(billing_res.target_file, check_drift=True)
        self.assertTrue(bill_report.is_valid)
        self.assertEqual(len(bill_report.drifts), 0)
        self.assertGreater(bill_report.total_contracts_count, 0)


if __name__ == "__main__":
    unittest.main()

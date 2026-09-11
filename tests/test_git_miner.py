import subprocess
import tempfile
import unittest
from pathlib import Path
from doclayer.git_miner import (
    parse_commits,
    extract_ticket_or_reference,
    _clean_rationale,
    mine_constant_origin,
    mine_negative_runbooks,
    discover_subsystems,
    COMMIT_DELIMITER,
)


class TestDoclayerGitMiner(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parse_commits(self):
        raw = f"""abc1234567890|abc1234|Alice|2026-09-01|feat: add connection pool
Why: prevent connection timeout during peak traffic
---
{COMMIT_DELIMITER}
def0987654321|def0987|Bob|2026-09-02|fix(db): resolve deadlock on commit INC-4921
Details of the bug
{COMMIT_DELIMITER}
"""
        records = parse_commits(raw)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].short_hash, "abc1234")
        self.assertEqual(records[0].author, "Alice")
        self.assertEqual(records[0].subject, "feat: add connection pool")
        self.assertIn("prevent connection timeout", records[0].body)

        self.assertEqual(records[1].short_hash, "def0987")
        self.assertEqual(records[1].subject, "fix(db): resolve deadlock on commit INC-4921")

    def test_extract_ticket_or_reference(self):
        self.assertEqual(extract_ticket_or_reference("Resolved INC-9901 in pool", "abc1234"), "INC-9901")
        self.assertEqual(extract_ticket_or_reference("Patch for CVE-2024-12345", "abc1234"), "CVE-2024-12345")
        self.assertEqual(extract_ticket_or_reference("Per RFC-42 design", "abc1234"), "RFC-42")
        self.assertEqual(extract_ticket_or_reference("Routine bump of retries", "abc1234"), "Commit: abc1234")

    def test_clean_rationale(self):
        r1 = _clean_rationale("feat(auth): increase token timeout", "Why: avoid token expiration on slow mobile networks")
        self.assertEqual(r1, "avoid token expiration on slow mobile networks")

        r2 = _clean_rationale("fix: prevent memory leak in worker pool", "")
        self.assertEqual(r2, "prevent memory leak in worker pool")

    def test_git_miner_on_real_repo(self):
        repo = self.tmp_path / "test-repo"
        repo.mkdir()

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=str(repo), capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "DocLayer Tester"], cwd=str(repo), capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "tester@doclayer.dev"], cwd=str(repo), capture_output=True, check=True)

        # 1. Commit with a constant
        src_dir = repo / "src" / "pool"
        src_dir.mkdir(parents=True)
        pool_file = src_dir / "pool.py"
        pool_file.write_text("MAX_POOL_WORKERS = 15\n", encoding="utf-8")

        subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "feat(pool): configure max pool workers\n\nWhy: prevent exhaustion during peak load (RFC-101)"],
            cwd=str(repo),
            capture_output=True,
            check=True
        )

        # 2. Revert commit to test negative runbook mining
        revert_file = src_dir / "danger.py"
        revert_file.write_text("# bypass check\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "feat: bypass rate limiting"], cwd=str(repo), capture_output=True, check=True)

        revert_file.unlink()
        subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Revert \"feat: bypass rate limiting\"\n\nCaused cascading outages INC-8822"],
            cwd=str(repo),
            capture_output=True,
            check=True
        )

        # Mine constant origin
        origin = mine_constant_origin("MAX_POOL_WORKERS", repo_path=repo)
        self.assertIsNotNone(origin)
        self.assertEqual(origin.symbol_name, "MAX_POOL_WORKERS")
        self.assertEqual(origin.reference, "RFC-101")
        self.assertIn("exhaustion during peak load", origin.rationale)
        self.assertEqual(origin.epistemic_status, "STATED")

        # Mine negative runbooks
        runbooks = mine_negative_runbooks(repo)
        self.assertTrue(len(runbooks) >= 1)
        revert_rb = next((r for r in runbooks if "revert" in r.symptom.lower() or "bypass rate limiting" in r.prohibited_actions.lower()), None)
        self.assertIsNotNone(revert_rb)
        self.assertIn("bypass rate limiting", revert_rb.prohibited_actions)
        self.assertEqual(revert_rb.reference, "INC-8822")

        # Discover subsystems
        discoveries = discover_subsystems(repo)
        self.assertEqual(len(discoveries), 1)
        self.assertEqual(discoveries[0].slug, "pool")
        self.assertEqual(discoveries[0].language, "python")
        self.assertIn("max_pool_workers", discoveries[0].constants)


if __name__ == "__main__":
    unittest.main()

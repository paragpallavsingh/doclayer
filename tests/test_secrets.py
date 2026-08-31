import tempfile
import unittest
from pathlib import Path
from doclayer.secrets import scan_for_secrets, check_for_config_keys
from doclayer.validator import validate_file


class TestDoclayerSecretsAndConfig(unittest.TestCase):
    def test_detects_hardcoded_api_key(self):
        content = "## Invariants\napi_key = 'AKIA1234567890ABCDEF'\npassword = 'supersecretpassword123'"
        violations = scan_for_secrets(content)
        self.assertTrue(len(violations) >= 2)
        rule_names = [v.rule_name for v in violations]
        self.assertIn("AWS Access Key ID", rule_names)

    def test_detects_github_pat(self):
        content = "token = 'ghp_1234567890abcdefghijklmnopqrstuvwxyzAB'\nfine_grained = 'github_pat_11AABBCCDDEEFFGGHHIIJJ_KKLLMMNNOOPPQQRRSSTTUUVVWWXXYYZZ0011223344556677889900'"
        violations = scan_for_secrets(content)
        self.assertEqual(len(violations), 2)
        rules = [v.rule_name for v in violations]
        self.assertIn("GitHub Personal Access Token", rules)
        self.assertIn("GitHub Fine-Grained Personal Access Token", rules)

    def test_detects_llm_api_keys(self):
        content = "openai_key = 'sk-proj-1234567890abcdef1234567890abcdef1234567890'\nanthropic_key = 'sk-ant-1234567890abcdef1234567890abcdef1234567890'"
        violations = scan_for_secrets(content)
        self.assertTrue(len(violations) >= 2)
        rules = [v.rule_name for v in violations]
        self.assertIn("OpenAI / LLM API Key", rules)
        self.assertIn("Anthropic API Key", rules)

    def test_detects_connection_string_credentials(self):
        content = "url = 'postgres://admin:secretpass123@db.internal:5432/orders'"
        violations = scan_for_secrets(content)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].rule_name, "Connection string with embedded credentials")

    def test_clean_layer_has_zero_secret_violations(self):
        content = """# Subsystem: Payment Engine
**Package:** `src/payment.py`
**Owner:** `@billing-team`
## 1. Overview
Clean documentation.
## 2. Invariants
```invariants
[invariants]
max_retries = 3
timeout_seconds = 5
```
"""
        violations = scan_for_secrets(content)
        self.assertEqual(len(violations), 0)

    def test_warns_on_environment_config_keys(self):
        invariants_data = {
            "invariants": {
                "max_retries": 3,
                "database_url": "postgres://localhost:5432/db",
                "redis_host": "cache.internal",
            }
        }
        warnings = check_for_config_keys(invariants_data)
        self.assertTrue(any("database_url" in w for w in warnings))
        self.assertTrue(any("redis_host" in w for w in warnings))


if __name__ == "__main__":
    unittest.main()

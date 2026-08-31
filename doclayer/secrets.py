"""
Zero-dependency Secret and Credential Scanner for doclayer.
Enforces the first-principles boundary: DocLayer never contains secrets or runtime credentials.
"""
import re
from dataclasses import dataclass
from typing import List

# Common credential signatures and secret patterns
SECRET_PATTERNS = [
    (re.compile(r"(?i)(password|passwd|secret|api[_-]?key|access[_-]?token|bearer[_-]?token|auth[_-]?token)\s*=\s*['\"][A-Za-z0-9_\-+/=]{8,}['\"]"), "Hardcoded password/token assignment"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS Access Key ID"),
    (re.compile(r"(?i)gh[pousr]_[A-Za-z0-9_]{36,255}"), "GitHub Personal Access Token"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{22,255}"), "GitHub Fine-Grained Personal Access Token"),
    (re.compile(r"sk-(?:proj-|svcacct-)?[A-Za-z0-9_\-]{32,}"), "OpenAI / LLM API Key"),
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{32,}"), "Anthropic API Key"),
    (re.compile(r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}[a-zA-Z0-9-]*"), "Slack API / Webhook Token"),
    (re.compile(r"-----BEGIN (?:[A-Z0-9_-]+ )?PRIVATE KEY-----"), "Private Cryptographic Key"),
    (re.compile(r"(?i)(postgres|mysql|redis|mongodb):\/\/[^:]+:[^@]+@"), "Connection string with embedded credentials"),
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9_\-\.]{20,}"), "Bearer authentication token"),
    (re.compile(r"eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*"), "JSON Web Token (JWT) signature"),
]

# Keys that look like environment config rather than architectural invariants
CONFIG_KEY_PATTERNS = [
    re.compile(r"(?i)(.*_url$|.*_endpoint$|.*_host$|.*_port$|aws_region|gcp_project|database_.*|redis_.*)"),
]


@dataclass
class SecretViolation:
    line_number: int
    rule_name: str
    snippet: str


def scan_for_secrets(content: str) -> List[SecretViolation]:
    """Scans text content for hardcoded credentials, private keys, or API tokens."""
    violations: List[SecretViolation] = []
    lines = content.splitlines()

    for idx, line in enumerate(lines, start=1):
        for pattern, rule_name in SECRET_PATTERNS:
            match = pattern.search(line)
            if match:
                # Mask secret snippet for safe error output
                raw = match.group(0)
                masked = raw[:6] + "..." + raw[-4:] if len(raw) > 12 else "***"
                violations.append(
                    SecretViolation(
                        line_number=idx,
                        rule_name=rule_name,
                        snippet=masked,
                    )
                )
    return violations


def check_for_config_keys(invariants_data: dict) -> List[str]:
    """Warns if keys appear to be environment/infrastructure configuration rather than invariants."""
    warnings: List[str] = []
    if not isinstance(invariants_data, dict):
        return warnings

    keys_to_check = []
    for k, v in invariants_data.items():
        if isinstance(v, dict):
            keys_to_check.extend(v.keys())
        else:
            keys_to_check.append(k)

    for k in keys_to_check:
        for pat in CONFIG_KEY_PATTERNS:
            if pat.match(k):
                warnings.append(
                    f"Key '{k}' looks like application environment configuration. "
                    "Rule: DocLayer stores engineering constraints, not environment config."
                )
    return warnings

from http.server import HTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.request

from doclayer.server import DoclayerRequestHandler


class TestDoclayerServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.tmp_path = Path(cls.temp_dir.name)
        cls.doclayer_dir = cls.tmp_path / ".doclayer"
        cls.doclayer_dir.mkdir()

        # Create a sample layer file
        layer_file = cls.doclayer_dir / "payment.md"
        layer_file.write_text("""# Subsystem: Payment Engine

**Package:** `src/payment.py`
**Owner:** `@payments` (Alerts: `EP-PAY`)

---

## 1. Overview & Topology
Payment processing subsystem.

## 2. Contracts & Invariants
```invariants
[invariants]
max_retries = 3
timeout_sec = 10
```
| Invariant / Contract | Why & Rationale | Reference | Evidence Anchor |
| :--- | :--- | :--- | :--- |
| `max_retries = 3` | Avoid gateway penalty | `RFC-101` | `src/payment.py::MAX_RETRIES` |
| `timeout_sec = 10` | Downstream SLA limit | `RFC-101` | `src/payment.py::TIMEOUT_SEC` |

## 3. Failure Modes & Agent Safety Runbook
| Symptom / Error | Probable Root Cause | Safe Remediation | Prohibited Actions (What NOT to do) | Reference |
| :--- | :--- | :--- | :--- | :--- |
| `ERR_GATEWAY` | Payment gateway latency | Retry with backoff | NEVER execute duplicate charge without idempotency key | `RFC-101` |

## 4. References
* Source: `src/payment.py`
""", encoding="utf-8")

        # Configure RequestHandler
        DoclayerRequestHandler.layer_dir = cls.doclayer_dir
        DoclayerRequestHandler.repo_root = cls.tmp_path

        # Start server on ephemeral port (port 0)
        cls.server = HTTPServer(("127.0.0.1", 0), DoclayerRequestHandler)
        cls.port = cls.server.server_port
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.temp_dir.cleanup()

    def test_get_index_html(self):
        url = f"http://127.0.0.1:{self.port}/"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("text/html", resp.headers.get("Content-Type", ""))
            content = resp.read().decode("utf-8")
            self.assertIn("DocLayer", content)
            self.assertIn("Local Hub", content)

    def test_api_status(self):
        url = f"http://127.0.0.1:{self.port}/api/status"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["total_subsystems"], 1)
            self.assertEqual(data["total_invariants"], 2)
            self.assertEqual(data["total_guardrails"], 1)
            self.assertEqual(len(data["subsystems"]), 1)
            self.assertEqual(data["subsystems"][0]["slug"], "payment")

    def test_api_subsystem_detail(self):
        url = f"http://127.0.0.1:{self.port}/api/subsystems/payment"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["title"], "Payment Engine")
            self.assertEqual(data["slug"], "payment")
            self.assertEqual(len(data["contracts"]), 2)
            self.assertEqual(len(data["runbooks"]), 1)
            self.assertIn("NEVER execute duplicate charge", data["runbooks"][0]["prohibited_actions"])
            self.assertIn("DOCLAYER HARNESS", data["explain_text"])


if __name__ == "__main__":
    unittest.main()

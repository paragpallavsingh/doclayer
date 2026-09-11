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

        # Load sample subsystem contract from existing dogfood examples
        import shutil
        example_src = Path(__file__).parent.parent / "examples" / "payment-engine.md"
        shutil.copy(example_src, cls.doclayer_dir / "payment.md")

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
            self.assertEqual(data["total_invariants"], 3)
            self.assertEqual(data["total_guardrails"], 2)
            self.assertEqual(len(data["subsystems"]), 1)
            self.assertEqual(data["subsystems"][0]["slug"], "payment")

    def test_api_subsystem_detail(self):
        url = f"http://127.0.0.1:{self.port}/api/subsystems/payment"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["title"], "Payment Engine & Stripe Settlement")
            self.assertEqual(data["slug"], "payment")
            self.assertEqual(len(data["contracts"]), 3)
            self.assertEqual(len(data["runbooks"]), 2)
            self.assertIn("NEVER issue refund", data["runbooks"][0]["prohibited_actions"])
            self.assertIn("DOCLAYER HARNESS", data["explain_text"])


if __name__ == "__main__":
    unittest.main()

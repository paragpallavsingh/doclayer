"""
doclayer serve: Embedded zero-dependency local web dashboard.
Provides an interactive DeepWiki-style browser experience with real-time
invariant status, AST drift detection, epistemic debt metrics, and agent safety runbooks.
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from pathlib import Path
import sys
import threading
from typing import Any, Dict, List, Optional
import urllib.parse
import webbrowser

from doclayer.parser import parse_layer_file
from doclayer.validator import validate_file, ValidationReport
from doclayer.git_miner import get_repo_root, mine_negative_runbooks

DEFAULT_BIND_ADDRESS = "127.0.0.1"
DEFAULT_PORT_NUMBER = 8080
DEFAULT_SERVER_HOST = DEFAULT_BIND_ADDRESS
DEFAULT_SERVER_PORT = DEFAULT_PORT_NUMBER


def get_dashboard_html() -> str:
    """Load the embedded DeepWiki web dashboard HTML template."""
    template_path = Path(__file__).parent / "templates" / "dashboard.html"
    if template_path.exists():
        return template_path.read_text(encoding="utf-8")
    return "<!DOCTYPE html><html><body><h1>DocLayer Dashboard</h1><p>Template not found.</p></body></html>"


HTML_TEMPLATE = get_dashboard_html()



class DoclayerRequestHandler(BaseHTTPRequestHandler):
    layer_dir: Path = Path(".doclayer")
    repo_root: Path = Path.cwd()

    def log_message(self, format: str, *args: Any) -> None:
        # Keep server silent for clean CLI experience
        return

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        if not path:
            path = "/index.html"

        if path in ("/index.html", "/"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))
            return

        if path == "/api/status":
            self.handle_api_status()
            return

        if path.startswith("/api/subsystems/"):
            slug = path[len("/api/subsystems/"):]
            self.handle_api_subsystem(slug)
            return

        if path == "/api/git/history":
            self.handle_api_git_history()
            return

        self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": "Not Found"}).encode("utf-8"))

    def handle_api_status(self) -> None:
        target_dir = self.layer_dir
        if not target_dir.exists() and Path("docs/layers").exists():
            target_dir = Path("docs/layers")

        layer_files = sorted(target_dir.glob("*.md")) if target_dir.exists() else []
        subsystems_summary: List[Dict[str, Any]] = []

        total_invs = 0
        total_drifts = 0
        total_stated = 0
        total_contracts = 0
        total_guardrails = 0

        for lf in layer_files:
            rep = validate_file(lf, check_drift=True)
            slug = lf.stem.lower()
            inv_count = rep.total_contracts_count
            drift_count = len(rep.drifts)
            subsystems_summary.append({
                "title": rep.title,
                "slug": slug,
                "package": rep.semantic_deps.upstream or lf.name,
                "invariant_count": inv_count,
                "drift_count": drift_count,
                "epistemic_certainty_pct": rep.epistemic_certainty_pct,
                "negative_runbooks_count": rep.negative_invariants_count,
            })
            total_invs += inv_count
            total_drifts += drift_count
            total_stated += rep.stated_count
            total_contracts += rep.total_contracts_count
            total_guardrails += rep.negative_invariants_count

        overall_epistemic = (
            round((total_stated / total_contracts * 100.0), 1) if total_contracts > 0 else 100.0
        )

        resp = {
            "total_subsystems": len(layer_files),
            "total_invariants": total_invs,
            "overall_epistemic_pct": overall_epistemic,
            "total_drifts": total_drifts,
            "total_guardrails": total_guardrails,
            "subsystems": subsystems_summary,
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(resp).encode("utf-8"))

    def handle_api_subsystem(self, slug: str) -> None:
        target_dir = self.layer_dir
        if not target_dir.exists() and Path("docs/layers").exists():
            target_dir = Path("docs/layers")

        target_file = target_dir / f"{slug}.md"
        if not target_file.exists():
            # Search case-insensitive
            for f in target_dir.glob("*.md"):
                if f.stem.lower() == slug.lower():
                    target_file = f
                    break

        if not target_file.exists():
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Subsystem '{slug}' not found"}).encode("utf-8"))
            return

        doc = parse_layer_file(target_file)
        rep = validate_file(target_file, check_drift=True)

        drifts_by_key = {d.invariant_key: d for d in rep.drifts}

        contracts_list = []
        for c in rep.contracts:
            inv_k = c.invariant_key or c.invariant_expr.split("=")[0].strip(" `")
            inv_v = None
            if "=" in c.invariant_expr:
                parts = c.invariant_expr.split("=", 1)
                inv_v = parts[1].strip(" `")
            elif doc.invariants_data and inv_k in doc.invariants_data:
                inv_v = doc.invariants_data[inv_k]

            clean_k = inv_k.lower()
            drift_item = drifts_by_key.get(clean_k)
            contracts_list.append({
                "key": inv_k,
                "doc_value": inv_v if inv_v is not None else c.invariant_expr,
                "code_value": drift_item.code_value if drift_item else inv_v,
                "has_drift": drift_item is not None,
                "epistemic_status": c.epistemic_status,
                "reference": c.reference,
                "evidence_anchor": c.evidence_anchor,
            })

        runbooks_list = []
        for r in rep.runbook_items:
            runbooks_list.append({
                "symptom": r.symptom,
                "cause": r.probable_cause,
                "safe_remediation": r.safe_remediation,
                "prohibited_actions": r.prohibited_actions,
                "reference": r.reference,
            })

        # Format explain context for quick copy (Contract + Verification State)
        explain_lines = [
            f"=== DOCLAYER HARNESS: {rep.title} ===",
            f"Package: {doc.package} | Owner: {doc.owner}",
            "",
            "Protocol:",
            "* If [VERIFIED]: Never introduce changes that cause contract drift.",
            "* If [DRIFT]: Do not silently adopt drifted code as truth or alter contracts without human elevation.",
            "",
            "1. Machine Invariants (Contract + Verification State):",
        ]
        for c in rep.contracts:
            inv_k = c.invariant_key or c.invariant_expr.split("=")[0].strip(" `")
            clean_k = inv_k.lower()
            drift_item = drifts_by_key.get(clean_k)
            if drift_item:
                explain_lines.append(f"  * {c.invariant_expr} [{c.epistemic_status}] [DRIFT] (Ref: {c.reference})")
                explain_lines.append(f"    --> Code AST = {drift_item.code_value} ({drift_item.file_path.name}:{drift_item.line_number})")
            else:
                explain_lines.append(f"  * {c.invariant_expr} [{c.epistemic_status}] [VERIFIED] (Ref: {c.reference})")
        explain_lines.append("")
        explain_lines.append("2. Prohibited Actions (What NOT to do):")
        for r in rep.runbook_items:
            if r.prohibited_actions:
                explain_lines.append(f"  * On {r.symptom}: {r.prohibited_actions}")

        resp = {
            "title": rep.title,
            "slug": target_file.stem.lower(),
            "package": doc.package or "src/",
            "owner": doc.owner or "@team",
            "epistemic_certainty_pct": rep.epistemic_certainty_pct,
            "contracts": contracts_list,
            "runbooks": runbooks_list,
            "explain_text": "\n".join(explain_lines),
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(resp).encode("utf-8"))

    def handle_api_git_history(self) -> None:
        runbooks = mine_negative_runbooks(self.repo_root, max_commits=30)
        data = [
            {
                "symptom": r.symptom,
                "cause": r.probable_cause,
                "safe_remediation": r.safe_remediation,
                "prohibited_actions": r.prohibited_actions,
                "reference": r.reference,
                "commit_hash": r.commit_hash,
            }
            for r in runbooks
        ]
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"incidents": data}).encode("utf-8"))


def start_server(
    host: str = DEFAULT_SERVER_HOST,
    port: int = DEFAULT_SERVER_PORT,
    layer_dir: Path = Path(".doclayer"),
    open_browser: bool = True,
) -> None:
    """Starts the DocLayer embedded HTTP server."""
    DoclayerRequestHandler.layer_dir = layer_dir
    DoclayerRequestHandler.repo_root = get_repo_root(layer_dir)

    server = HTTPServer((host, port), DoclayerRequestHandler)
    url = f"http://{host}:{port}"
    print(f"\033[92m\033[1m[OK] DocLayer Local Hub running at:\033[0m \033[96m{url}\033[0m")
    print(f"  Layer Directory:  {layer_dir}")
    print(f"  Press Ctrl+C to terminate.")

    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping DocLayer server...")
        server.server_close()

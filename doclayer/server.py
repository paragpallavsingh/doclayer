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


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DocLayer | Engineering Context & Safety Harness</title>
  <style>
    :root {
      --bg: #0f172a;
      --card-bg: #1e293b;
      --card-border: #334155;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --accent: #38bdf8;
      --accent-hover: #0284c7;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.5;
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }
    header {
      background-color: #0b1120;
      border-bottom: 1px solid var(--card-border);
      padding: 12px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      font-weight: 700;
      font-size: 1.15rem;
      letter-spacing: -0.025em;
    }
    .brand span {
      background: linear-gradient(135deg, #38bdf8, #818cf8);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .badge-hub {
      background-color: rgba(56, 189, 248, 0.15);
      color: #38bdf8;
      padding: 2px 8px;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
    }
    .stats-bar {
      display: flex;
      gap: 20px;
      font-size: 0.85rem;
    }
    .stat-item {
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .stat-val { font-weight: 700; color: #fff; }
    .layout {
      display: flex;
      flex: 1;
      overflow: hidden;
    }
    aside {
      width: 280px;
      background-color: #0d1526;
      border-right: 1px solid var(--card-border);
      display: flex;
      flex-direction: column;
    }
    .aside-header {
      padding: 16px;
      border-bottom: 1px solid var(--card-border);
    }
    .aside-search {
      width: 100%;
      background: #1e293b;
      border: 1px solid var(--card-border);
      border-radius: 6px;
      padding: 8px 12px;
      color: var(--text);
      font-size: 0.85rem;
      outline: none;
    }
    .aside-search:focus { border-color: var(--accent); }
    .subsystem-list {
      flex: 1;
      overflow-y: auto;
      list-style: none;
      padding: 8px;
    }
    .subsystem-btn {
      width: 100%;
      text-align: left;
      background: transparent;
      border: 1px solid transparent;
      border-radius: 6px;
      padding: 10px 12px;
      color: var(--text-muted);
      cursor: pointer;
      display: flex;
      flex-direction: column;
      gap: 4px;
      transition: all 0.15s ease;
      margin-bottom: 4px;
    }
    .subsystem-btn:hover {
      background: rgba(255, 255, 255, 0.04);
      color: var(--text);
    }
    .subsystem-btn.active {
      background: rgba(56, 189, 248, 0.1);
      border-color: rgba(56, 189, 248, 0.3);
      color: #38bdf8;
    }
    .subsystem-title { font-weight: 600; font-size: 0.9rem; }
    .subsystem-meta { font-size: 0.75rem; display: flex; gap: 8px; opacity: 0.8; }
    main {
      flex: 1;
      overflow-y: auto;
      padding: 24px 32px;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }
    .subsystem-hero {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      border-bottom: 1px solid var(--card-border);
      padding-bottom: 16px;
    }
    .hero-title h1 { font-size: 1.6rem; font-weight: 700; margin-bottom: 4px; }
    .hero-meta { display: flex; gap: 16px; font-size: 0.85rem; color: var(--text-muted); }
    .hero-meta code { color: var(--accent); font-family: var(--font-mono); }
    .btn-action {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      color: var(--text);
      padding: 8px 14px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.85rem;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 8px;
      transition: all 0.15s ease;
    }
    .btn-action:hover { background: #2d3748; border-color: var(--accent); }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 20px;
    }
    .card-title {
      font-size: 1.05rem;
      font-weight: 700;
      margin-bottom: 14px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.85rem;
      text-align: left;
    }
    th, td {
      padding: 10px 12px;
      border-bottom: 1px solid var(--card-border);
    }
    th { color: var(--text-muted); font-weight: 600; text-transform: uppercase; font-size: 0.75rem; letter-spacing: 0.05em; }
    tr:last-child td { border-bottom: none; }
    code {
      font-family: var(--font-mono);
      background: rgba(0, 0, 0, 0.3);
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 0.85em;
    }
    .tag {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 0.75rem;
      font-weight: 700;
    }
    .tag-stated { background: rgba(16, 185, 129, 0.2); color: #10b981; }
    .tag-unreferenced { background: rgba(245, 158, 11, 0.2); color: #f59e0b; }
    .tag-inferred { background: rgba(129, 140, 248, 0.2); color: #818cf8; }
    .tag-drift { background: rgba(239, 68, 68, 0.2); color: #ef4444; }
    .tag-ok { background: rgba(16, 185, 129, 0.2); color: #10b981; }
    .runbook-grid {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .runbook-card {
      background: #162032;
      border: 1px solid var(--card-border);
      border-left: 4px solid var(--danger);
      border-radius: 6px;
      padding: 14px 16px;
    }
    .runbook-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
    }
    .prohibited-alert {
      background: rgba(239, 68, 68, 0.1);
      border: 1px solid rgba(239, 68, 68, 0.3);
      color: #fca5a5;
      padding: 8px 12px;
      border-radius: 4px;
      font-size: 0.85rem;
      margin-top: 8px;
      font-weight: 600;
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="#38bdf8"/>
      </svg>
      <span>DocLayer</span>
      <div class="badge-hub">Local Hub</div>
    </div>
    <div class="stats-bar" id="globalStats">
      <div class="stat-item">Subsystems: <span class="stat-val" id="statSubsystems">-</span></div>
      <div class="stat-item">Invariants: <span class="stat-val" id="statInvariants">-</span></div>
      <div class="stat-item">Epistemic Certainty: <span class="stat-val" id="statEpistemic">-</span></div>
      <div class="stat-item">AST Drifts: <span class="stat-val" id="statDrifts">-</span></div>
    </div>
  </header>

  <div class="layout">
    <aside>
      <div class="aside-header">
        <input type="text" class="aside-search" id="subsystemSearch" placeholder="Search subsystems..." />
      </div>
      <ul class="subsystem-list" id="subsystemsContainer"></ul>
    </aside>

    <main id="contentContainer">
      <div style="display: flex; align-items: center; justify-content: center; height: 100%; color: var(--text-muted);">
        Loading subsystem context...
      </div>
    </main>
  </div>

  <script>
    let currentData = null;
    let activeSlug = null;

    async function fetchStatus() {
      try {
        const res = await fetch('/api/status');
        currentData = await res.json();
        renderHeaderStats(currentData);
        renderSidebar(currentData.subsystems);
        if (currentData.subsystems.length > 0) {
          selectSubsystem(activeSlug || currentData.subsystems[0].slug);
        }
      } catch (err) {
        console.error('Failed to fetch status:', err);
      }
    }

    function renderHeaderStats(data) {
      document.getElementById('statSubsystems').innerText = data.total_subsystems;
      document.getElementById('statInvariants').innerText = data.total_invariants;
      document.getElementById('statEpistemic').innerText = data.overall_epistemic_pct + '%';
      const driftEl = document.getElementById('statDrifts');
      driftEl.innerText = data.total_drifts;
      driftEl.style.color = data.total_drifts > 0 ? '#ef4444' : '#10b981';
    }

    function renderSidebar(subsystems) {
      const container = document.getElementById('subsystemsContainer');
      const query = document.getElementById('subsystemSearch').value.toLowerCase();
      container.innerHTML = '';

      subsystems
        .filter(s => s.title.toLowerCase().includes(query) || s.slug.includes(query))
        .forEach(s => {
          const li = document.createElement('li');
          li.innerHTML = `
            <button class="subsystem-btn ${s.slug === activeSlug ? 'active' : ''}" onclick="selectSubsystem('${s.slug}')">
              <span class="subsystem-title">${s.title}</span>
              <div class="subsystem-meta">
                <span>${s.invariant_count} invs</span>
                <span>•</span>
                <span>${s.epistemic_certainty_pct}% stated</span>
                ${s.drift_count > 0 ? `<span class="tag tag-drift" style="padding:1px 4px;font-size:0.65rem;">DRIFT</span>` : ''}
              </div>
            </button>
          `;
          container.appendChild(li);
        });
    }

    async function selectSubsystem(slug) {
      activeSlug = slug;
      renderSidebar(currentData.subsystems);
      const main = document.getElementById('contentContainer');
      main.innerHTML = '<div style="color:var(--text-muted);padding:24px;">Loading details...</div>';

      try {
        const res = await fetch(`/api/subsystems/${slug}`);
        const sub = await res.json();
        renderSubsystemView(sub);
      } catch (err) {
        main.innerHTML = `<div style="color:#ef4444;">Failed to load subsystem ${slug}</div>`;
      }
    }

    function renderSubsystemView(sub) {
      const main = document.getElementById('contentContainer');
      const contractsRows = sub.contracts.map(c => `
        <tr>
          <td><code>${c.key}</code></td>
          <td><code>${JSON.stringify(c.doc_value)}</code></td>
          <td><code>${c.code_value !== undefined ? JSON.stringify(c.code_value) : '-'}</code></td>
          <td>
            ${c.has_drift 
              ? `<span class="tag tag-drift">DRIFT</span>` 
              : `<span class="tag tag-ok">VERIFIED</span>`}
          </td>
          <td>
            <span class="tag tag-${c.epistemic_status.toLowerCase()}">${c.epistemic_status}</span>
          </td>
          <td><code>${c.reference}</code></td>
          <td><span style="font-size:0.8rem;color:var(--text-muted);">${c.evidence_anchor}</span></td>
        </tr>
      `).join('');

      const runbookCards = sub.runbooks.map(r => `
        <div class="runbook-card">
          <div class="runbook-header">
            <strong>${r.symptom}</strong>
            <span class="tag tag-stated">${r.reference}</span>
          </div>
          <div style="font-size:0.85rem;color:var(--text-muted);margin-bottom:6px;">
            <strong>Cause:</strong> ${r.cause} | <strong>Remediation:</strong> ${r.safe_remediation}
          </div>
          <div class="prohibited-alert">
            🛑 PROHIBITED: ${r.prohibited_actions}
          </div>
        </div>
      `).join('');

      main.innerHTML = `
        <div class="subsystem-hero">
          <div class="hero-title">
            <h1>${sub.title}</h1>
            <div class="hero-meta">
              <span>Package: <code>${sub.package}</code></span>
              <span>Owner: <code>${sub.owner}</code></span>
              <span>Epistemic Grounding: <strong>${sub.epistemic_certainty_pct}%</strong></span>
            </div>
          </div>
          <button class="btn-action" onclick="copyAgentPrompt()">
            <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
            </svg>
            Copy Agent Harness Context
          </button>
        </div>

        <div class="card">
          <div class="card-title">
            <span>Machine-Checked Invariants & Contracts</span>
            <span style="font-size:0.85rem;font-weight:400;color:var(--text-muted);">
              ${sub.contracts.length} active invariants
            </span>
          </div>
          <table>
            <thead>
              <tr>
                <th>Invariant Key</th>
                <th>Contract Value</th>
                <th>Code AST Value</th>
                <th>Drift Status</th>
                <th>Epistemic Tier</th>
                <th>Reference</th>
                <th>Evidence Anchor</th>
              </tr>
            </thead>
            <tbody>
              ${contractsRows || '<tr><td colspan="7" style="text-align:center;color:var(--text-muted);">No declared invariants</td></tr>'}
            </tbody>
          </table>
        </div>

        <div class="card">
          <div class="card-title">
            <span>Agent Safety Runbook & Negative Invariants</span>
            <span style="font-size:0.85rem;font-weight:400;color:#fca5a5;">
              Active Prohibitions Enforced
            </span>
          </div>
          <div class="runbook-grid">
            ${runbookCards || '<div style="color:var(--text-muted);">No negative runbooks recorded.</div>'}
          </div>
        </div>
      `;

      window.currentExplainText = sub.explain_text;
    }

    function copyAgentPrompt() {
      if (window.currentExplainText) {
        navigator.clipboard.writeText(window.currentExplainText);
        alert('Copied DocLayer Agent Harness context to clipboard! Ready to paste into Cursor / Devin / Claude.');
      }
    }

    document.getElementById('subsystemSearch').addEventListener('input', () => {
      if (currentData) renderSidebar(currentData.subsystems);
    });

    fetchStatus();
    setInterval(fetchStatus, 5000);
  </script>
</body>
</html>
"""


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

        # Format explain context for quick copy
        explain_lines = [
            f"=== DOCLAYER HARNESS: {rep.title} ===",
            f"Package: {doc.package} | Owner: {doc.owner}",
            "",
            "1. Machine Invariants:",
        ]
        for c in rep.contracts:
            explain_lines.append(f"  * {c.invariant_expr} [{c.epistemic_status}] (Ref: {c.reference})")
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
    host: str = "127.0.0.1",
    port: int = 8080,
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

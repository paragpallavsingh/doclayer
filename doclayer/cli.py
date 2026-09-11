"""
doclayer CLI: Developer and Agent harness for living engineering subsystem layers.
"""
import argparse
from pathlib import Path
import subprocess
import sys
from typing import List, Optional

from doclayer import __version__
from doclayer.parser import parse_layer_file, LayerDocument
from doclayer.validator import validate_file, validate_layer_doc, ValidationReport, KnowledgeDebtItem
from doclayer.rca import inject_rca_record

# ANSI Color Codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def get_template_path() -> Path:
    """Finds the subsystem.md template path."""
    # 1. Package bundled template (doclayer/templates/subsystem.md)
    pkg_template = Path(__file__).parent / "templates" / "subsystem.md"
    if pkg_template.exists():
        return pkg_template
    # 2. Local dev template fallback
    local_template = Path("doclayer") / "templates" / "subsystem.md"
    if local_template.exists():
        return local_template
    return pkg_template


def cmd_init(args: argparse.Namespace) -> int:
    """Scaffolds a new subsystem markdown layer or initializes workspace."""
    subsystem = getattr(args, "subsystem", None)
    output_dir = Path(args.dir)

    # Workspace-level init (no subsystem provided)
    if not subsystem:
        target_dir = output_dir
        if args.dir == ".doclayer" and not target_dir.exists() and Path("docs/layers").exists():
            target_dir = Path("docs/layers")

        layers = sorted(target_dir.glob("*.md")) if target_dir.exists() else []
        dir_display = target_dir.as_posix()
        if not dir_display.endswith("/"):
            dir_display += "/"

        if target_dir.exists() and layers:
            count = len(layers)
            layer_str = f"{count} layer{'s' if count != 1 else ''} found"
            print(f"{GREEN}{BOLD}[OK] doclayer already initialized in {dir_display} ({layer_str}):{RESET}")
            for layer in layers:
                print(f"  - {layer.name}")
            print("Next steps:")
            print("  - Run 'doclayer check' to validate invariants.")
            print("  - Run 'doclayer explain <file>' to view active contracts.")
            print("  - Run 'doclayer init <name>' to scaffold a new subsystem.")
            return 0

        target_dir.mkdir(parents=True, exist_ok=True)
        print(f"{GREEN}{BOLD}[OK] Initialized empty doclayer workspace in {dir_display}{RESET}")
        print("Next steps:")
        print("  - Run 'doclayer init <name>' to scaffold a new subsystem.")
        print("  - Run 'doclayer check' to validate invariants.")
        return 0

    subsystem_slug = subsystem.lower().replace(" ", "-").replace("_", "-")
    target_file = output_dir / f"{subsystem_slug}.md"

    if target_file.exists() and not args.force:
        print(f"{RED}Error: Layer file already exists at {target_file}. Use --force to overwrite.{RESET}")
        return 1

    template_path = get_template_path()
    if not template_path.exists():
        print(f"{RED}Error: Subsystem template not found at {template_path}.{RESET}")
        return 1

    content = template_path.read_text(encoding="utf-8-sig")
    title = args.title or subsystem.replace("-", " ").replace("_", " ").title()
    package_path = args.package or f"src/modules/{subsystem_slug}/"
    owner_team = args.owner or f"@{subsystem_slug}-team"
    alert_channel = args.alert or f"EP-{subsystem_slug.upper()}-TIER1"
    client_class = "".join(word.capitalize() for word in subsystem_slug.split("-")) + "Client"

    # Replace placeholders
    content = content.replace("{{SUBSYSTEM_TITLE}}", title)
    content = content.replace("{{PACKAGE_PATH}}", package_path)
    content = content.replace("{{OWNER_TEAM}}", owner_team)
    content = content.replace("{{ALERT_CHANNEL}}", alert_channel)
    content = content.replace("{{OVERVIEW_DESCRIPTION}}", f"Handles core operations, contracts, and lifecycle for {title}.")
    content = content.replace("{{CLIENT_CLASS}}", client_class)
    content = content.replace("{{IMPORT_PATH}}", f"@/modules/{subsystem_slug}")

    output_dir.mkdir(parents=True, exist_ok=True)
    target_file.write_text(content, encoding="utf-8")

    print(f"{GREEN}{BOLD}[OK] Initialized doclayer subsystem:{RESET} {CYAN}{target_file}{RESET}")
    print(f"  Title:   {title}")
    print(f"  Package: {package_path}")
    print(f"  Owner:   {owner_team}")
    return 0


def get_git_changed_files(git_ref: Optional[str] = None, staged: bool = False, repo_dir: Optional[Path] = None) -> Optional[List[str]]:
    """Gets list of changed file paths using git diff."""
    cwd_str = str(repo_dir) if repo_dir and repo_dir.exists() else None
    try:
        if staged:
            cmd = ["git", "diff", "--name-only", "--cached"]
        elif git_ref:
            cmd = ["git", "diff", "--name-only", git_ref]
        else:
            cmd = ["git", "diff", "--name-only", "HEAD"]

        res = subprocess.run(cmd, cwd=cwd_str, capture_output=True, text=True, check=False)
        if res.returncode != 0:
            return None

        changed = [line.strip().replace("\\", "/") for line in res.stdout.splitlines() if line.strip()]
        
        # Also grab untracked files
        status_res = subprocess.run(["git", "status", "--porcelain"], cwd=cwd_str, capture_output=True, text=True, check=False)
        if status_res.returncode == 0:
            for line in status_res.stdout.splitlines():
                line = line.strip()
                if line.startswith("??"):
                    untracked = line[2:].strip().replace("\\", "/")
                    if untracked not in changed:
                        changed.append(untracked)
        return changed
    except Exception:
        return None


def resolve_layers_for_changed_files(layers_dir: Path, changed_files: List[str]) -> List[Path]:
    """
    Identifies which subsystem layer files to scan based on changed files:
    1. Direct layer markdown edits (.doclayer/<subsystem>.md or docs/layers/<subsystem>.md)
    2. Source package edits matching a layer's declared '**Package:**' metadata.
    """
    all_layers = sorted(layers_dir.glob("*.md")) if layers_dir.exists() else []
    matched_layers = set()

    # Pre-parse layers to get package paths
    layer_docs = [(lp, parse_layer_file(lp)) for lp in all_layers]

    for changed in changed_files:
        changed_clean = changed.replace("\\", "/").strip("/")
        # Check if changed file is a layer doc directly
        for lp, doc in layer_docs:
            lp_clean = lp.as_posix().strip("/")
            if lp_clean == changed_clean or lp.name == Path(changed).name:
                matched_layers.add(lp)
                continue

            # Check if changed file belongs to layer's declared package
            if doc.package:
                pkg_clean = doc.package.replace("\\", "/").strip("/")
                if changed_clean.startswith(pkg_clean) or pkg_clean in changed_clean:
                    matched_layers.add(lp)

    return sorted(list(matched_layers))


def cmd_check(args: argparse.Namespace) -> int:
    """Validates markdown subsystem layers, invariant fences, and surfaces knowledge debt."""
    path_arg = Path(args.path)
    files_to_check: List[Path] = []

    # If --changed or --since or --staged is requested, filter using git diff
    if getattr(args, "changed", False) or getattr(args, "since", None) or getattr(args, "staged", False):
        layers_dir = path_arg if path_arg.is_dir() else (Path(".doclayer") if Path(".doclayer").exists() else Path("docs/layers"))
        
        # Discover repository root by walking up for .git
        repo_dir = Path.cwd()
        if layers_dir.exists():
            curr = layers_dir.resolve()
            for _ in range(5):
                if (curr / ".git").exists():
                    repo_dir = curr
                    break
                if curr.parent == curr:
                    break
                curr = curr.parent

        git_ref = getattr(args, "since", None)
        staged = getattr(args, "staged", False)
        
        changed_files = get_git_changed_files(git_ref=git_ref, staged=staged, repo_dir=repo_dir)
        if changed_files is not None:
            files_to_check = resolve_layers_for_changed_files(layers_dir, changed_files)
            if not files_to_check:
                print(f"{GREEN}[OK]{RESET} No subsystem layer or managed package files changed. Skipping invariant checks.")
                return 0
            print(f"{CYAN}Git Diff Filter:{RESET} Detected {len(changed_files)} changed file(s) -> Mapped to {len(files_to_check)} relevant subsystem layer(s).\n")
        else:
            print(f"{YELLOW}Warning: Git repository not detected or git command unavailable. Falling back to directory scan.{RESET}")

    if not files_to_check:
        if path_arg.is_file():
            files_to_check.append(path_arg)
        elif path_arg.is_dir():
            files_to_check.extend(sorted(path_arg.glob("*.md")))
            if not files_to_check:
                files_to_check.extend(sorted(path_arg.glob("**/*.md")))
        else:
            default_dir = Path(".doclayer") if Path(".doclayer").exists() else Path("docs/layers")
            if default_dir.exists():
                files_to_check.extend(sorted(default_dir.glob("*.md")))

    if not files_to_check:
        print(f"{YELLOW}No subsystem layer markdown files found in {path_arg}.{RESET}")
        return 0

    total_files = len(files_to_check)
    passed = 0
    failed = 0
    all_reports: List[ValidationReport] = []

    print(f"{BOLD}doclayer check:{RESET} Inspecting {total_files} subsystem layer file(s)...\n")

    is_strict = getattr(args, "strict", False)

    for file_path in files_to_check:
        report = validate_file(file_path)
        all_reports.append(report)
        rel_path = file_path.as_posix()

        has_drift_violation = is_strict and len(report.drifts) > 0
        if report.is_valid and not has_drift_violation:
            passed += 1
            print(f" {GREEN}[PASS]{RESET}  {BOLD}{rel_path}{RESET} ({report.title})")
            if report.invariants:
                inv_keys = list(report.invariants.keys())
                print(f"         {CYAN}Invariants verified:{RESET} {', '.join(inv_keys)}")
            if report.negative_invariants_count > 0:
                print(f"         {MAGENTA}Safety runbooks:{RESET} {report.negative_invariants_count} negative invariant guardrails active")
            for w in report.warnings:
                print(f"         {YELLOW}Warning:{RESET} {w}")
            for d in report.drifts:
                print(f"         {YELLOW}[DRIFT DETECTED]{RESET} Invariant '{d.invariant_key}': DocLayer={d.doc_value} vs Code AST={d.code_value} ({d.file_path.name}:{d.line_number})")
        else:
            failed += 1
            status_tag = f"{RED}[FAIL (STRICT DRIFT)]{RESET}" if (report.is_valid and has_drift_violation) else f"{RED}[FAIL]{RESET}"
            print(f" {status_tag}  {BOLD}{rel_path}{RESET} ({report.title})")
            for err in report.errors:
                print(f"         {RED}Error:{RESET} {err}")
            for w in report.warnings:
                print(f"         {YELLOW}Warning:{RESET} {w}")
            for d in report.drifts:
                drift_tag = f"{RED}[STRICT DRIFT ERROR]{RESET}" if is_strict else f"{YELLOW}[DRIFT DETECTED]{RESET}"
                print(f"         {drift_tag} Invariant '{d.invariant_key}': DocLayer={d.doc_value} vs Code AST={d.code_value} ({d.file_path.name}:{d.line_number})")
        print()

    print("-" * 60)
    if failed == 0:
        print(f"{GREEN}{BOLD}All {passed} subsystem layers passed invariant and contract checks.{RESET}")
    else:
        print(f"{RED}{BOLD}Failed {failed} of {total_files} subsystem layer(s).{RESET}")

    # Knowledge Debt Summary (if --debt flag passed or unreferenced contracts exist)
    show_debt = getattr(args, "debt", False)
    total_unref = sum(r.unreferenced_count for r in all_reports)
    total_inferred = sum(r.inferred_count for r in all_reports)
    total_contracts = sum(r.total_contracts_count for r in all_reports)

    if show_debt or (total_unref + total_inferred > 0 and show_debt):
        print(f"\n{BOLD}Knowledge Debt & Epistemic Audit:{RESET}")
        overall_certainty = round((sum(r.stated_count for r in all_reports) / max(total_contracts, 1)) * 100.0, 1)
        print(f"  Overall Epistemic Certainty: {CYAN}{overall_certainty}%{RESET} ({total_contracts - total_unref - total_inferred}/{total_contracts} grounded)")
        print(f"  Unreferenced Invariants:     {YELLOW}{total_unref}{RESET}")
        print(f"  Inferred Heuristics:        {MAGENTA}{total_inferred}{RESET}\n")

        all_debt_items = [item for r in all_reports for item in r.knowledge_debt]
        if all_debt_items:
            print(f"  {BOLD}{'Subsystem':<22} | {'Invariant':<30} | {'Status':<12} | {'Action Required'}{RESET}")
            print("  " + "-" * 90)
            for item in all_debt_items:
                status_color = YELLOW if item.epistemic_status == "UNREFERENCED" else MAGENTA
                print(f"  {item.subsystem_title[:22]:<22} | {item.invariant_expr[:30]:<30} | {status_color}{item.epistemic_status:<12}{RESET} | {item.action_prompt}")
            print()

    return 0 if failed == 0 else 1


def cmd_inspect(args: argparse.Namespace) -> int:
    """Inspects a subsystem's full governance profile, contracts, dependencies, and agent safety runbooks."""
    subsystem = args.subsystem
def find_layer_for_target(target: str, layers_dir: Optional[Path] = None) -> Optional[Path]:
    """
    Locates the governing doclayer markdown specification for a target:
    - Direct layer markdown path
    - Subsystem slug / name
    - Source code file path (mapped via 'Package:' metadata header)
    """
    target_path = Path(target)
    if target_path.is_file() and target_path.suffix == ".md":
        return target_path

    search_dirs: List[Path] = []
    if layers_dir and layers_dir.exists():
        search_dirs.append(layers_dir)
    if Path(".doclayer").exists():
        search_dirs.append(Path(".doclayer"))
    if Path("docs/layers").exists():
        search_dirs.append(Path("docs/layers"))
    if Path("examples").exists():
        search_dirs.append(Path("examples"))

    # 1. Direct name / slug matching (only .md files)
    target_stem = Path(target).stem
    slug = target_stem.lower().replace(" ", "-").replace("_", "-")
    for d in search_dirs:
        for name_cand in [f"{target_stem}.md", f"{slug}.md", f"{target}.md"]:
            cand = d / name_cand
            if cand.is_file() and cand.suffix == ".md":
                return cand

    # 2. Package path resolution (match source code file to declared Package)
    target_clean = target.replace("\\", "/").strip("/")
    for d in search_dirs:
        for md_file in sorted(d.glob("*.md")):
            doc = parse_layer_file(md_file)
            if doc.package:
                pkg_clean = doc.package.replace("\\", "/").strip("/")
                if target_clean == pkg_clean or target_clean.startswith(pkg_clean) or pkg_clean in target_clean:
                    return md_file

    return None


def cmd_explain(args: argparse.Namespace) -> int:
    """Explains active contracts, negative invariant safety prohibitions, drift, and epistemic status for a target."""
    target = args.target
    layers_dir = Path(args.path) if hasattr(args, "path") and args.path else None
    layer_file = find_layer_for_target(target, layers_dir=layers_dir)

    if not layer_file or not layer_file.exists():
        if getattr(args, "json", False):
            import json
            print(json.dumps({"error": f"No governing DocLayer subsystem found for '{target}'", "target": target}, indent=2))
        else:
            print(f"{RED}Error: No governing DocLayer subsystem layer found for '{target}'.{RESET}")
            print(f"Tip: Run 'doclayer init {Path(target).stem}' to establish a contract layer.")
        return 1

    report = validate_file(layer_file)
    doc = parse_layer_file(layer_file)

    if getattr(args, "json", False):
        import json
        payload = {
            "subsystem": report.title,
            "layer_file": layer_file.as_posix(),
            "package": doc.package,
            "owner": doc.owner,
            "epistemic_certainty_pct": report.epistemic_certainty_pct,
            "contracts": [
                {
                    "invariant": c.invariant_expr,
                    "rationale": c.rationale,
                    "reference": c.reference,
                    "anchor": c.evidence_anchor,
                    "status": c.epistemic_status,
                }
                for c in report.contracts
            ],
            "safety_prohibitions": [
                {
                    "symptom": item.symptom,
                    "probable_cause": item.probable_cause,
                    "safe_remediation": item.safe_remediation,
                    "prohibited_actions": item.prohibited_actions,
                    "reference": item.reference,
                }
                for item in report.runbook_items
            ],
            "safety_invariants": report.semantic_deps.safety_invariants,
            "safety_firewalls": report.semantic_deps.safety_invariants,
            "drift_status": "PASS" if not report.drifts else "DRIFT_DETECTED",
            "drifts": [
                {
                    "key": d.invariant_key,
                    "doc_value": d.doc_value,
                    "code_value": d.code_value,
                    "file": d.file_path.name,
                    "line": d.line_number,
                }
                for d in report.drifts
            ],
            "knowledge_debt": [
                {
                    "invariant": item.invariant_expr,
                    "status": item.epistemic_status,
                    "action_required": item.action_prompt,
                }
                for item in report.knowledge_debt
            ],
        }
        print(json.dumps(payload, indent=2))
        return 0

    print(f"\n{BOLD}{'=' * 78}{RESET}")
    print(f" {CYAN}{BOLD}DOCLAYER GOVERNANCE CONTRACT:{RESET} {BOLD}{report.title}{RESET}")
    print(f"{BOLD}{'=' * 78}{RESET}")
    print(f"  {BOLD}Governing Spec:{RESET}   {layer_file.as_posix()}")
    print(f"  {BOLD}Package Root:{RESET}     {doc.package or 'Unspecified'}")
    print(f"  {BOLD}Owner:{RESET}            {doc.owner or 'Unassigned'}")
    print(f"  {BOLD}Epistemic Score:{RESET}  {CYAN}{report.epistemic_certainty_pct}% Stated{RESET} ({report.stated_count} stated, {report.inferred_count} inferred, {report.unreferenced_count} unreferenced)")

    # 1. Active Contracts & Invariants
    print(f"\n{BOLD}1. Declared Invariant Contracts ({len(report.contracts)}):{RESET}")
    if report.contracts:
        for c in report.contracts:
            status_tag = f"{GREEN}[STATED]{RESET}" if c.epistemic_status == "STATED" else (f"{MAGENTA}[INFERRED]{RESET}" if c.epistemic_status == "INFERRED" else f"{YELLOW}[UNREFERENCED]{RESET}")
            print(f"  * {BOLD}{c.invariant_expr}{RESET} {status_tag}")
            print(f"    Why: {c.rationale} ({c.reference})")
    else:
        print(f"  {DIM}No formal invariant rows parsed.{RESET}")

    # 2. Negative Invariants & Prohibitions (Safety Harness)
    print(f"\n{BOLD}2. Agent Safety Harness & Prohibited Actions:{RESET}")
    if report.runbook_items:
        for item in report.runbook_items:
            if item.prohibited_actions and item.prohibited_actions.strip() != "None specified":
                print(f"  * {RED}{BOLD}PROHIBITED:{RESET} {RED}{item.prohibited_actions}{RESET}")
                print(f"    On Error: `{item.symptom}` -> Safe Action: {item.safe_remediation}")
    else:
        print(f"  {DIM}No negative invariant prohibitions declared.{RESET}")

    if report.semantic_deps.safety_invariants:
        print(f"  * {BOLD}Active Safety Invariants:{RESET} {', '.join(report.semantic_deps.safety_invariants)}")

    # 3. Real-Time AST Drift Status
    print(f"\n{BOLD}3. Real-Time AST Drift Status:{RESET}")
    if not report.drifts:
        print(f"  {GREEN}[PASS]{RESET} Source code constants are fully aligned with declared DocLayer contracts.")
    else:
        print(f"  {RED}{BOLD}[DRIFT DETECTED]{RESET} {len(report.drifts)} contract(s) diverge from implementation AST:")
        for d in report.drifts:
            print(f"    - Invariant '{d.invariant_key}': DocLayer={d.doc_value} vs Code={d.code_value} ({d.file_path.name}:{d.line_number})")

    # 4. Knowledge Debt Prompts
    if report.knowledge_debt:
        print(f"\n{YELLOW}{BOLD}4. Actionable Knowledge Debt ({len(report.knowledge_debt)}):{RESET}")
        for item in report.knowledge_debt:
            print(f"  [ ] {item.invariant_expr} ({item.epistemic_status}): {item.action_prompt}")

    print()
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    """Inspects a subsystem's full governance profile, contracts, dependencies, and agent safety runbooks."""
    subsystem = args.subsystem
    layers_dir = Path(args.path) if hasattr(args, "path") and args.path else None
    layer_file = find_layer_for_target(subsystem, layers_dir=layers_dir)

    if not layer_file or not layer_file.exists():
        print(f"{RED}Error: Subsystem layer not found for '{subsystem}'.{RESET}")
        return 1

    report = validate_file(layer_file)
    doc = parse_layer_file(layer_file)

    print(f"\n{BOLD}{'=' * 78}{RESET}")
    print(f" {CYAN}{BOLD}SUBSYSTEM GOVERNANCE PROFILE:{RESET} {BOLD}{report.title}{RESET}")
    print(f"{BOLD}{'=' * 78}{RESET}")
    print(f"  {BOLD}File:{RESET}             {layer_file.as_posix()}")
    print(f"  {BOLD}Package Root:{RESET}     {doc.package or 'Unspecified'}")
    print(f"  {BOLD}Owner:{RESET}            {doc.owner or 'Unassigned'}")
    print(f"  {BOLD}Epistemic Score:{RESET}  {CYAN}{report.epistemic_certainty_pct}% Stated{RESET} ({report.stated_count} stated, {report.inferred_count} inferred, {report.unreferenced_count} unreferenced)")

    # 1. Semantic Dependencies
    print(f"\n{BOLD}1. Semantic Topology & Dependencies:{RESET}")
    deps = report.semantic_deps
    print(f"  * {BOLD}Upstream Callers:{RESET}     {', '.join(deps.upstream) if deps.upstream else 'None declared'}")
    print(f"  * {BOLD}Downstream Targets:{RESET}   {', '.join(deps.downstream) if deps.downstream else 'None declared'}")
    if deps.state_dependencies:
        print(f"  * {BOLD}State Dependencies:{RESET}   {', '.join(deps.state_dependencies)}")
    if deps.identity_invariants:
        print(f"  * {BOLD}Identity Invariants:{RESET}  {', '.join(deps.identity_invariants)}")
    if deps.safety_invariants:
        print(f"  * {BOLD}Safety Invariants:{RESET}     {', '.join(deps.safety_invariants)}")

    # 2. Invariant Contracts Table
    print(f"\n{BOLD}2. Declared Machine Contracts & Invariants ({len(report.contracts)}):{RESET}")
    if report.contracts:
        for c in report.contracts:
            status_tag = f"{GREEN}[STATED]{RESET}" if c.epistemic_status == "STATED" else (f"{MAGENTA}[INFERRED]{RESET}" if c.epistemic_status == "INFERRED" else f"{YELLOW}[UNREFERENCED]{RESET}")
            print(f"  * {BOLD}{c.invariant_expr}{RESET} {status_tag}")
            print(f"    Rationale: {c.rationale}")
            print(f"    Ref:       {c.reference} | Anchor: {c.evidence_anchor}")
    else:
        print(f"  {DIM}No formal contract table rows parsed.{RESET}")

    # 3. Agent Safety Runbook (Negative Invariants)
    print(f"\n{BOLD}3. Agent Safety Runbook & Prohibitions ({len(report.runbook_items)}):{RESET}")
    if report.runbook_items:
        for item in report.runbook_items:
            print(f"  * {BOLD}Symptom:{RESET} {item.symptom}")
            print(f"    Cause:       {item.probable_cause}")
            print(f"    Remediation: {item.safe_remediation}")
            if item.prohibited_actions and item.prohibited_actions.strip() != "None specified":
                print(f"    {RED}{BOLD}PROHIBITED (What NOT to do):{RESET} {RED}{item.prohibited_actions}{RESET}")
            print()
    else:
        print(f"  {DIM}No operational runbook items parsed.{RESET}")

    # 4. Knowledge Debt Call to Action
    if report.knowledge_debt:
        print(f"{YELLOW}{BOLD}Actionable Knowledge Debt:{RESET}")
        for item in report.knowledge_debt:
            print(f"  [ ] {item.invariant_expr} ({item.epistemic_status}): {item.action_prompt}")
        print()

    return 0


def cmd_rca(args: argparse.Namespace) -> int:
    """Appends an incident-derived architectural decision and invariant into the subsystem layer."""
    subsystem = args.subsystem
    layers_dir = Path(args.path) if hasattr(args, "path") and args.path else (Path(".doclayer") if Path(".doclayer").exists() else Path("docs/layers"))

    layer_file: Optional[Path] = None
    if Path(subsystem).is_file():
        layer_file = Path(subsystem)
    else:
        candidates = [
            layers_dir / f"{subsystem}.md",
            layers_dir / f"{subsystem.lower().replace(' ', '-')}.md",
            Path(".doclayer") / f"{subsystem}.md",
            Path(".doclayer") / f"{subsystem.lower().replace(' ', '-')}.md",
            Path("docs/layers") / f"{subsystem}.md",
            Path("docs/layers") / f"{subsystem.lower().replace(' ', '-')}.md",
        ]
        for c in candidates:
            if c.exists():
                layer_file = c
                break

    if not layer_file or not layer_file.exists():
        print(f"{RED}Error: Subsystem layer file not found for '{subsystem}'.{RESET}")
        return 1

    success, msg = inject_rca_record(
        file_path=layer_file,
        incident_id=args.incident,
        decision=args.decision,
        rationale=args.rationale,
        invariant_pair=args.invariant,
        symptom=args.symptom,
        remediation=args.remediation,
        prohibited=getattr(args, "prohibited", None),
        anchor=getattr(args, "anchor", None),
    )

    if not success:
        print(f"{RED}Error updating layer:{RESET} {msg}")
        return 1

    # Validate the file after mutation to guarantee correctness
    report = validate_file(layer_file)
    if not report.is_valid:
        print(f"{RED}Warning: Layer file mutated but failed validation:{RESET}")
        for err in report.errors:
            print(f"  - {err}")
        return 1

    print(f"{GREEN}{BOLD}[OK] RCA Record Injected Successfully{RESET}")
    print(f"  Subsystem:  {CYAN}{layer_file}{RESET}")
    print(f"  Incident:   {BOLD}{args.incident}{RESET}")
    print(f"  Decision:   {args.decision}")
    print(f"  Rationale:  {args.rationale}")
    if args.invariant:
        print(f"  Invariant:  {args.invariant}")
    if getattr(args, "prohibited", None):
        print(f"  Prohibited: {RED}{args.prohibited}{RESET}")
    return 0


def cmd_auto(args: argparse.Namespace) -> int:
    """Discovers repo subsystems, extracts polyglot constants & git history, and synthesizes contracts."""
    repo_path = Path(args.path).resolve()
    output_dir = Path(args.dir)

    print(f"{BOLD}doclayer auto: Synthesizing contracts from codebase & git history...{RESET}")
    print(f"  Target:     {CYAN}{repo_path}{RESET}")
    print(f"  Output Dir: {CYAN}{output_dir}{RESET}")

    from doclayer.auto import synthesize_repo_layers

    results = synthesize_repo_layers(
        repo_path=repo_path,
        output_dir=output_dir,
        force=args.force,
        dry_run=args.dry_run,
    )

    if not results:
        print(f"{YELLOW}No source modules or code constants discovered.{RESET}")
        return 0

    success_count = 0
    print()
    for res in results:
        if res.created:
            success_count += 1
            print(f" {GREEN}{BOLD}[SYNTHESIZED]{RESET} {BOLD}{res.target_file}{RESET}")
            print(f"               Slug: {res.subsystem_slug} | Epistemic Grounding: {res.epistemic_score}% Stated")
            print(f"               Invariants: {res.invariant_count} | Negative Runbooks: {res.negative_runbook_count}")
        else:
            print(f" {YELLOW}[SKIPPED]{RESET}     {res.target_file} - {res.message}")

    print()
    if args.dry_run:
        print(f"{CYAN}{BOLD}[DRY RUN COMPLETE]{RESET} {len(results)} subsystem(s) evaluated.")
        return 0

    print(f"{GREEN}{BOLD}[OK] Synthesis complete:{RESET} Generated {success_count} of {len(results)} subsystem layer(s).")
    print("Next steps:")
    print("  - Run 'doclayer check' to verify all synthesized invariants.")
    print("  - Run 'doclayer serve' to explore the DeepWiki browser UI.")
    print("  - Run 'doclayer explain <subsystem>' for agent context.")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    """Launches embedded zero-dependency local web dashboard."""
    layer_dir = Path(args.path)
    if not layer_dir.exists() and Path("docs/layers").exists():
        layer_dir = Path("docs/layers")

    from doclayer.server import start_server

    start_server(
        host=args.host,
        port=args.port,
        layer_dir=layer_dir,
        open_browser=not args.no_browser,
    )
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="doclayer",
        description="doclayer: Living engineering context harness for software subsystems."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

    # auto (The Synthesis Command)
    auto_parser = subparsers.add_parser("auto", help="Synthesize subsystem contracts from polyglot code & git history")
    auto_parser.add_argument("path", nargs="?", default=".", help="Target repository or module path (default: .)")
    auto_parser.add_argument("--dir", default=".doclayer", help="Destination directory (default: .doclayer)")
    auto_parser.add_argument("-f", "--force", action="store_true", help="Overwrite existing layer files")
    auto_parser.add_argument("--dry-run", action="store_true", help="Preview synthesized contracts without writing to disk")
    auto_parser.set_defaults(func=cmd_auto)

    # serve (DeepWiki Embedded Local Web UI)
    serve_parser = subparsers.add_parser("serve", help="Launch embedded local web dashboard (DeepWiki browser)")
    serve_parser.add_argument("--port", type=int, default=8080, help="HTTP port (default: 8080)")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    serve_parser.add_argument("--path", default=".doclayer", help="Path to layer directory (default: .doclayer)")
    serve_parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    serve_parser.set_defaults(func=cmd_serve)

    # explain (Primary Agent & Developer Entry Point)
    explain_parser = subparsers.add_parser("explain", help="Explain active contracts, safety prohibitions, and drift for a file or subsystem")
    explain_parser.add_argument("target", help="Subsystem name, slug, or source file path (e.g., src/janitor.py)")
    explain_parser.add_argument("--path", default=None, help="Directory containing layer files")
    explain_parser.add_argument("--json", action="store_true", help="Output machine-readable JSON for agent tool integration")
    explain_parser.set_defaults(func=cmd_explain)

    # init
    init_parser = subparsers.add_parser("init", help="Scaffold a new subsystem markdown layer or initialize workspace")
    init_parser.add_argument("subsystem", nargs="?", default=None, help="Subsystem name or slug (e.g., payment, auth-router)")
    init_parser.add_argument("--dir", default=".doclayer", help="Destination directory (default: .doclayer)")
    init_parser.add_argument("--title", help="Human-readable title")
    init_parser.add_argument("--package", help="Target source package path")
    init_parser.add_argument("--owner", help="Owner team tag")
    init_parser.add_argument("--alert", help="Alert channel")
    init_parser.add_argument("-f", "--force", action="store_true", help="Overwrite existing layer file")
    init_parser.set_defaults(func=cmd_init)

    # check
    check_parser = subparsers.add_parser("check", help="Parse and validate subsystem layers & invariants")
    check_parser.add_argument("--path", default=".doclayer", help="File or directory to validate (default: .doclayer)")
    check_parser.add_argument("--changed", action="store_true", help="Only check layers affected by uncommitted or recent git changes")
    check_parser.add_argument("--since", help="Git reference or base branch to compare against (e.g., origin/main or HEAD~1)")
    check_parser.add_argument("--staged", action="store_true", help="Only check layers affected by git staged changes (for pre-commit)")
    check_parser.add_argument("--debt", action="store_true", help="Surface actionable Knowledge Debt and unreferenced invariant prompts")
    check_parser.add_argument("--strict", action="store_true", help="Enforce strict CI mode (fail with non-zero exit code if AST invariant drift is detected)")
    check_parser.set_defaults(func=cmd_check)

    # inspect
    inspect_parser = subparsers.add_parser("inspect", help="Inspect a subsystem's full governance profile and safety runbooks")
    inspect_parser.add_argument("subsystem", help="Subsystem name, slug, or file path")
    inspect_parser.add_argument("--path", default=".doclayer", help="Directory containing layer files")
    inspect_parser.set_defaults(func=cmd_inspect)

    # rca
    rca_parser = subparsers.add_parser("rca", help="Inject post-mortem lessons into subsystem layer")
    rca_parser.add_argument("--subsystem", required=True, help="Subsystem name or file path")
    rca_parser.add_argument("--incident", required=True, help="Incident or ticket reference ID (e.g. INC-4819)")
    rca_parser.add_argument("--decision", required=True, help="Architectural decision / constraint added")
    rca_parser.add_argument("--rationale", required=True, help="Root cause rationale and tradeoff explanation")
    rca_parser.add_argument("--invariant", help="Key-value pair to update in invariants fence (e.g. timeout_ms=1200)")
    rca_parser.add_argument("--symptom", help="Optional error code or symptom to add to runbook")
    rca_parser.add_argument("--remediation", help="Immediate remediation command for runbook")
    rca_parser.add_argument("--prohibited", help="Prohibited actions (What NOT to do) for agent safety")
    rca_parser.add_argument("--anchor", help="Source code evidence anchor (e.g. src/payment.py::TIMEOUT)")
    rca_parser.add_argument("--path", default=".doclayer", help="Directory containing layer files")
    rca_parser.set_defaults(func=cmd_rca)

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

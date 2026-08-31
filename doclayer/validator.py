"""
Validation rules, diagnostics, knowledge debt analysis, and security engine for doclayer subsystem layers.
Checks structure, TOML invariants syntax, epistemic rationales, negative runbook invariants, file existence, secret leaks, and AST code drift.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from doclayer.parser import (
    LayerDocument,
    parse_layer_file,
    parse_markdown_table,
    ContractItem,
    RunbookItem,
    SemanticDependencies,
)
from doclayer.drift import detect_invariant_drift, DriftItem
from doclayer.secrets import scan_for_secrets, check_for_config_keys, SecretViolation

CORE_SECTIONS: Dict[int, str] = {
    1: "Overview & Topology",
    2: "Contracts & Invariants",
    3: "Failure Modes & Agent Safety Runbook",
    4: "References",
}


@dataclass
class KnowledgeDebtItem:
    subsystem_title: str
    file_path: Path
    invariant_expr: str
    evidence_anchor: str
    epistemic_status: str  # "UNREFERENCED" or "INFERRED"
    action_prompt: str


@dataclass
class ValidationReport:
    file_path: Path
    title: str
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    invariants: Dict[str, Any] = field(default_factory=dict)
    drifts: List[DriftItem] = field(default_factory=list)
    secret_violations: List[SecretViolation] = field(default_factory=list)
    knowledge_debt: List[KnowledgeDebtItem] = field(default_factory=list)
    contracts: List[ContractItem] = field(default_factory=list)
    runbook_items: List[RunbookItem] = field(default_factory=list)
    semantic_deps: SemanticDependencies = field(default_factory=SemanticDependencies)
    epistemic_certainty_pct: float = 100.0
    total_contracts_count: int = 0
    unreferenced_count: int = 0
    inferred_count: int = 0
    stated_count: int = 0
    negative_invariants_count: int = 0


def _find_source_files_for_doc(doc: LayerDocument) -> List[Path]:
    """Resolves physical source files referenced by the document."""
    sources: List[Path] = []
    if not doc.package:
        return sources

    pkg_str = doc.package.strip()
    pkg_path = Path(pkg_str)
    
    valid_extensions = ["*.py", "*.ts", "*.tsx", "*.js", "*.jsx", "*.go", "*.rs"]

    def _collect_from_dir(d: Path) -> List[Path]:
        collected = []
        for ext in valid_extensions:
            collected.extend(d.glob(f"**/{ext}"))
        if not collected:
            # Fallback: any non-hidden files in directory
            collected.extend([f for f in d.glob("**/*") if f.is_file() and not f.name.startswith(".")])
        return sorted(list(set(collected)))

    # 1. Direct path check
    if pkg_path.is_file():
        return [pkg_path]
    elif pkg_path.is_dir():
        return _collect_from_dir(pkg_path)

    # 2. Walk up parent directories from doc location to find repo root
    current = doc.path.parent
    for _ in range(4):
        candidate = current / pkg_str
        if candidate.is_file():
            return [candidate]
        elif candidate.is_dir():
            return _collect_from_dir(candidate)
        if current.parent == current:
            break
        current = current.parent

    return sources


def validate_layer_doc(doc: LayerDocument, check_drift: bool = True) -> ValidationReport:
    """Validates structural constraints, file existence, secret leaks, epistemic rationales, and checks invariant drift."""
    errors: List[str] = list(doc.parse_errors)
    warnings: List[str] = []
    drifts: List[DriftItem] = []
    secret_violations: List[SecretViolation] = []
    knowledge_debt: List[KnowledgeDebtItem] = []

    # 1. Secret & Credential Scan (First-principles boundary: No secrets in DocLayer)
    if doc.raw_content:
        secret_violations = scan_for_secrets(doc.raw_content)
        for sv in secret_violations:
            errors.append(f"[SECURITY VIOLATION] Line {sv.line_number}: {sv.rule_name} detected ('{sv.snippet}'). Secrets must never be committed to DocLayer.")

    # 2. Title check
    if not doc.title:
        errors.append("Missing subsystem title (expected '# Subsystem: <Title>')")

    # 3. Metadata check
    if not doc.package:
        warnings.append("Missing '**Package:**' metadata field")
    if not doc.owner:
        warnings.append("Missing '**Owner:**' metadata field")

    # 4. Minimum mandatory section count (Overview, Contracts, Runbook)
    if len(doc.sections) < 3:
        errors.append(f"Subsystem layer has only {len(doc.sections)} sections. Expected core sections (Overview & Topology, Contracts & Invariants, Failure Modes & Runbook, References).")

    # 5. Invariants check & Config key linter
    if doc.invariants_data is None:
        if not any("```invariants" in err for err in errors):
            errors.append("Invalid or unparseable ```invariants block in Section 2/Contracts.")
    else:
        if not isinstance(doc.invariants_data, dict):
            errors.append("Invariants TOML root must be a table/dictionary")
        else:
            # Check if user accidentally put application config instead of architectural invariants
            config_warnings = check_for_config_keys(doc.invariants_data)
            warnings.extend(config_warnings)

    # 6. Check referenced source files existence on disk
    src_files = _find_source_files_for_doc(doc)
    if doc.package and not src_files:
        warnings.append(f"Referenced package/source path '{doc.package}' was not found on disk.")

    # 7. AST Code Drift Detection
    if check_drift and doc.invariants_data and src_files:
        has_py_files = any(f.suffix == ".py" for f in src_files)
        if not has_py_files:
            warnings.append(f"Package '{doc.package}' contains non-Python source files. AST drift checks currently active for Python (.py); polyglot AST scanners (TypeScript, Go, Rust) scheduled for v0.2.")
        else:
            drifts = detect_invariant_drift(doc.invariants_data, src_files)

    # 8. Epistemic Rationale & Knowledge Debt Calculation
    total_contracts = len(doc.contracts)
    stated_count = 0
    inferred_count = 0
    unreferenced_count = 0

    for contract in doc.contracts:
        if contract.epistemic_status == "STATED":
            stated_count += 1
        elif contract.epistemic_status == "INFERRED":
            inferred_count += 1
            knowledge_debt.append(
                KnowledgeDebtItem(
                    subsystem_title=doc.title or doc.path.name,
                    file_path=doc.path,
                    invariant_expr=contract.invariant_expr,
                    evidence_anchor=contract.evidence_anchor or doc.package,
                    epistemic_status="INFERRED",
                    action_prompt=f"Heuristic inference '{contract.rationale}'. Confirm or ground in official ADR/RFC before finalizing PR.",
                )
            )
        elif contract.epistemic_status == "UNREFERENCED":
            unreferenced_count += 1
            knowledge_debt.append(
                KnowledgeDebtItem(
                    subsystem_title=doc.title or doc.path.name,
                    file_path=doc.path,
                    invariant_expr=contract.invariant_expr,
                    evidence_anchor=contract.evidence_anchor or doc.package,
                    epistemic_status="UNREFERENCED",
                    action_prompt=f"Constraint observed in code without institutional reference. Attach 1-line author rationale or decision reference.",
                )
            )

    epistemic_certainty = (
        (stated_count / total_contracts * 100.0) if total_contracts > 0 else 100.0
    )

    # 9. Negative Runbook Invariants count
    negative_invariants_count = sum(1 for item in doc.runbook_items if item.prohibited_actions.strip())

    is_valid = len(errors) == 0
    return ValidationReport(
        file_path=doc.path,
        title=doc.title or doc.path.name,
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        invariants=doc.invariants_data or {},
        drifts=drifts,
        secret_violations=secret_violations,
        knowledge_debt=knowledge_debt,
        contracts=doc.contracts,
        runbook_items=doc.runbook_items,
        semantic_deps=doc.semantic_deps,
        epistemic_certainty_pct=round(epistemic_certainty, 1),
        total_contracts_count=total_contracts,
        unreferenced_count=unreferenced_count,
        inferred_count=inferred_count,
        stated_count=stated_count,
        negative_invariants_count=negative_invariants_count,
    )


def validate_file(file_path: Path, check_drift: bool = True) -> ValidationReport:
    """Convenience helper to parse and validate a file directly."""
    doc = parse_layer_file(file_path)
    return validate_layer_doc(doc, check_drift=check_drift)

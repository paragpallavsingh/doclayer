"""
Markdown, Invariant Block, and Epistemic Rationale Parser for doclayer subsystem documents.
"""
from dataclasses import dataclass, field
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        import toml as tomllib  # type: ignore

INVARIANTS_FENCE_REGEX = re.compile(
    r"```(?:invariants|toml)\s*\n(.*?)```",
    re.DOTALL | re.IGNORECASE
)

SECTION_HEADER_REGEX = re.compile(
    r"^##\s+(\d+)\.\s+(.*)$",
    re.MULTILINE
)


@dataclass
class LayerSection:
    number: int
    title: str
    content: str
    start_line: int
    end_line: int


@dataclass
class ContractItem:
    invariant_expr: str
    rationale: str
    reference: str
    evidence_anchor: str
    epistemic_status: str  # "STATED", "INFERRED", or "UNREFERENCED"
    invariant_key: str = ""


@dataclass
class RunbookItem:
    symptom: str
    probable_cause: str
    safe_remediation: str
    prohibited_actions: str  # Negative Invariant / What NOT to do
    reference: str


@dataclass
class SemanticDependencies:
    upstream: List[str] = field(default_factory=list)
    downstream: List[str] = field(default_factory=list)
    state_dependencies: List[str] = field(default_factory=list)
    identity_invariants: List[str] = field(default_factory=list)
    safety_firewalls: List[str] = field(default_factory=list)


@dataclass
class LayerDocument:
    path: Path
    raw_content: str
    title: str = ""
    package: str = ""
    owner: str = ""
    status: str = ""
    sections: Dict[int, LayerSection] = field(default_factory=dict)
    raw_invariants: Optional[str] = None
    invariants_data: Optional[Dict[str, Any]] = None
    contracts: List[ContractItem] = field(default_factory=list)
    runbook_items: List[RunbookItem] = field(default_factory=list)
    semantic_deps: SemanticDependencies = field(default_factory=SemanticDependencies)
    parse_errors: List[str] = field(default_factory=list)


def extract_invariants_fence(content: str) -> Optional[str]:
    """Extracts raw string inside the ```invariants code fence."""
    match = INVARIANTS_FENCE_REGEX.search(content)
    if match:
        return match.group(1).strip()
    return None


def parse_invariants_toml(toml_str: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Parses TOML invariant string into a Python dict."""
    try:
        data = tomllib.loads(toml_str)
        return data, None
    except Exception as e:
        return None, f"TOML parse error: {e}"


def parse_markdown_table(table_text: str) -> List[Dict[str, str]]:
    """Parses a standard markdown table into a list of row dictionaries."""
    lines = [l.strip() for l in table_text.splitlines() if l.strip().startswith("|")]
    if len(lines) < 3:
        return []
    
    # Extract headers
    headers = [col.strip() for col in lines[0].strip("|").split("|")]
    # line 1 is separator (e.g., | :--- | :--- |)
    rows: List[Dict[str, str]] = []
    for line in lines[2:]:
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) == len(headers):
            rows.append(dict(zip(headers, cols)))
    return rows


def classify_epistemic_status(rationale: str, reference: str) -> str:
    """
    Classifies the epistemic rationale status into:
    - STATED: Verified author/ADR/RFC/INC/DOC reference
    - INFERRED: Heuristic rationale deduced by LLM or tooling (prefixed or tagged [INFERRED])
    - UNREFERENCED: Known implementation truth whose institutional rationale has not yet been established
    """
    ref_upper = reference.strip().upper()
    rat_upper = rationale.strip().upper()

    if "[INFERRED]" in ref_upper or "[INFERRED]" in rat_upper or ref_upper.startswith("INFERRED"):
        return "INFERRED"
    
    if "UNREFERENCED" in ref_upper or "UNKNOWN" in ref_upper or not reference.strip() or ref_upper == "`UNREFERENCED`":
        return "UNREFERENCED"

    # Recognized formal references: RFC, ADR, INC, DOC, PR, ISSUE, etc.
    formal_prefixes = ("RFC", "ADR", "INC", "DOC", "PR", "ISSUE", "SPEC", "HIPAA", "DISHA")
    clean_ref = reference.strip("`").strip()
    if any(clean_ref.upper().startswith(p) for p in formal_prefixes) or "HTTP" in clean_ref.upper():
        return "STATED"

    # Default to STATED if specific reference text is provided
    return "STATED"


def extract_contracts_from_section(section_content: str) -> List[ContractItem]:
    """Parses Section 2 Contracts table and extracts epistemic contract items."""
    contracts: List[ContractItem] = []
    rows = parse_markdown_table(section_content)

    for row in rows:
        # Match flexible header names
        inv_expr = row.get("Invariant / Contract") or row.get("Invariant") or row.get("Contract") or ""
        rationale = row.get("Why & Rationale") or row.get("Rationale") or row.get("Why") or ""
        ref = row.get("Reference") or row.get("Source") or "UNREFERENCED"
        anchor = row.get("Evidence Anchor") or row.get("Evidence") or row.get("Anchor") or ""

        if not inv_expr:
            continue

        clean_expr = inv_expr.strip("`").strip()
        key = clean_expr.split("=")[0].strip() if "=" in clean_expr else clean_expr
        status = classify_epistemic_status(rationale, ref)

        contracts.append(
            ContractItem(
                invariant_expr=clean_expr,
                rationale=rationale,
                reference=ref,
                evidence_anchor=anchor,
                epistemic_status=status,
                invariant_key=key,
            )
        )
    return contracts


def extract_runbook_from_section(section_content: str) -> List[RunbookItem]:
    """Parses Section 3 Runbook table including negative invariants (Prohibited Actions)."""
    items: List[RunbookItem] = []
    rows = parse_markdown_table(section_content)

    for row in rows:
        symptom = row.get("Symptom / Error") or row.get("Symptom") or row.get("Error") or ""
        cause = row.get("Probable Root Cause") or row.get("Probable Cause") or row.get("Cause") or ""
        remediation = row.get("Verified Remediation") or row.get("Safe Remediation") or row.get("Remediation") or ""
        prohibited = (
            row.get("Prohibited Actions (What NOT to do)")
            or row.get("Prohibited Actions")
            or row.get("What NOT to do")
            or row.get("Negative Invariants")
            or ""
        )
        ref = row.get("Reference") or "UNREFERENCED"

        if symptom or cause or remediation:
            items.append(
                RunbookItem(
                    symptom=symptom,
                    probable_cause=cause,
                    safe_remediation=remediation,
                    prohibited_actions=prohibited,
                    reference=ref,
                )
            )
    return items


def extract_semantic_dependencies(inv_data: Optional[Dict[str, Any]]) -> SemanticDependencies:
    """Extracts typed upstream, downstream, state, identity, and firewall dependencies."""
    if not inv_data or not isinstance(inv_data, dict):
        return SemanticDependencies()

    deps_dict = inv_data.get("dependencies", {})
    if not isinstance(deps_dict, dict):
        return SemanticDependencies()

    def _to_list(val: Any) -> List[str]:
        if isinstance(val, list):
            return [str(x) for x in val]
        elif isinstance(val, str):
            return [val]
        return []

    return SemanticDependencies(
        upstream=_to_list(deps_dict.get("upstream")),
        downstream=_to_list(deps_dict.get("downstream")),
        state_dependencies=_to_list(deps_dict.get("state_dependencies") or deps_dict.get("state")),
        identity_invariants=_to_list(deps_dict.get("identity_invariants") or deps_dict.get("identity")),
        safety_firewalls=_to_list(deps_dict.get("safety_firewalls") or deps_dict.get("firewalls")),
    )


def parse_layer_file(file_path: Path) -> LayerDocument:
    """Reads and parses a doclayer markdown file into a full epistemic document model."""
    try:
        content = file_path.read_text(encoding="utf-8-sig")
    except Exception as e:
        doc = LayerDocument(path=file_path, raw_content="", parse_errors=[f"Failed to read file: {e}"])
        return doc

    doc = LayerDocument(path=file_path, raw_content=content)
    lines = content.splitlines()

    # Title extraction (# Subsystem: <title>)
    for line in lines[:10]:
        if line.startswith("# Subsystem:"):
            doc.title = line.replace("# Subsystem:", "").strip()
            break
        elif line.startswith("# "):
            doc.title = line[2:].strip()
            break

    # Metadata extraction
    for line in lines[:20]:
        line_s = line.strip()
        if line_s.startswith("**Package:**"):
            doc.package = line_s.replace("**Package:**", "").strip().strip("`")
        elif line_s.startswith("**Owner:**"):
            doc.owner = line_s.replace("**Owner:**", "").strip()
        elif line_s.startswith("**Status:**"):
            doc.status = line_s.replace("**Status:**", "").strip()

    # Sections parsing
    matches = list(SECTION_HEADER_REGEX.finditer(content))
    for i, match in enumerate(matches):
        section_num = int(match.group(1))
        section_title = match.group(2).strip()
        start_idx = match.end()
        end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        sec_content = content[start_idx:end_idx].strip()
        
        start_line = content[:match.start()].count("\n") + 1
        end_line = content[:end_idx].count("\n") + 1

        doc.sections[section_num] = LayerSection(
            number=section_num,
            title=section_title,
            content=sec_content,
            start_line=start_line,
            end_line=end_line,
        )

    # Invariants fence extraction & parsing
    raw_inv = extract_invariants_fence(content)
    doc.raw_invariants = raw_inv
    if raw_inv:
        inv_data, err = parse_invariants_toml(raw_inv)
        if err:
            doc.parse_errors.append(err)
        else:
            doc.invariants_data = inv_data
            doc.semantic_deps = extract_semantic_dependencies(inv_data)
    else:
        doc.parse_errors.append("Missing ```invariants code fence block in Section 2/Contracts.")

    # Extract Contracts & Epistemic Status (Section 2 or any section matching 'Contract' or 'Invariant')
    sec_2 = doc.sections.get(2)
    if sec_2:
        doc.contracts = extract_contracts_from_section(sec_2.content)
    else:
        for sec in doc.sections.values():
            if "contract" in sec.title.lower() or "invariant" in sec.title.lower():
                doc.contracts = extract_contracts_from_section(sec.content)
                break

    # Extract Runbook & Negative Invariants (Section 3 or any section matching 'Runbook' or 'Failure')
    sec_3 = doc.sections.get(3)
    if sec_3:
        doc.runbook_items = extract_runbook_from_section(sec_3.content)
    else:
        for sec in doc.sections.values():
            if "runbook" in sec.title.lower() or "failure" in sec.title.lower():
                doc.runbook_items = extract_runbook_from_section(sec.content)
                break

    return doc

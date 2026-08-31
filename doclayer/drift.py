"""
AST-based Invariant Drift Detector for doclayer.
Compares machine-readable invariants in docs/layers against actual code constants.
"""
import ast
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class DriftItem:
    invariant_key: str
    doc_value: Any
    code_value: Any
    file_path: Path
    symbol_name: str
    line_number: int


def _normalize_key(name: str) -> str:
    """Normalizes CONSTANT_NAME to lowercase key for fuzzy matching."""
    s = name.lower()
    if s.startswith("max_"):
        return s[4:]
    return s


def extract_constants_from_python_file(file_path: Path) -> Dict[str, Tuple[Any, str, int]]:
    """
    Parses a Python file using the standard library `ast` module
    and extracts top-level constant assignments.
    Returns: {normalized_key: (value, raw_symbol_name, line_number)}
    """
    if not file_path.exists() or file_path.suffix != ".py":
        return {}

    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8-sig"), filename=str(file_path))
    except Exception:
        return {}

    constants: Dict[str, Tuple[Any, str, int]] = {}

    for node in tree.body:
        # Match simple assignments: CONSTANT = value
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    sym_name = target.id
                    val = _ast_value_to_literal(node.value)
                    if val is not None:
                        # Store exact lower and normalized key
                        constants[sym_name.lower()] = (val, sym_name, node.lineno)
                        norm = _normalize_key(sym_name)
                        constants[norm] = (val, sym_name, node.lineno)

    return constants


def _ast_value_to_literal(node: ast.AST) -> Any:
    """Safely converts basic AST literal nodes to Python primitives."""
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, (ast.List, ast.Tuple)):
        return [_ast_value_to_literal(elt) for elt in node.elts]
    elif isinstance(node, ast.Set):
        return sorted([_ast_value_to_literal(elt) for elt in node.elts if _ast_value_to_literal(elt) is not None])
    return None


def detect_invariant_drift(
    invariants_data: Dict[str, Any],
    source_files: List[Path],
) -> List[DriftItem]:
    """
    Scans source files and compares extracted code constants against doc invariants.
    """
    drifts: List[DriftItem] = []
    if not invariants_data or not isinstance(invariants_data, dict):
        return drifts

    # Flatten invariants (e.g. runtime.timeout_seconds -> timeout_seconds or invariants.foo.value -> foo)
    flattened_invariants: Dict[str, Any] = {}
    for k, v in invariants_data.items():
        if isinstance(v, dict):
            for sub_k, sub_v in v.items():
                if isinstance(sub_v, dict) and "value" in sub_v:
                    val = sub_v["value"]
                else:
                    val = sub_v
                flattened_invariants[sub_k.lower()] = val
                flattened_invariants[_normalize_key(sub_k)] = val
        else:
            flattened_invariants[k.lower()] = v
            flattened_invariants[_normalize_key(k)] = v

    for src_file in source_files:
        code_constants = extract_constants_from_python_file(src_file)

        for inv_key, doc_val in flattened_invariants.items():
            if inv_key in code_constants:
                code_val, sym_name, lineno = code_constants[inv_key]

                # Compare values
                # Handle set/list comparisons
                if isinstance(doc_val, list) and isinstance(code_val, list):
                    match = sorted(doc_val) == sorted(code_val)
                else:
                    match = doc_val == code_val

                if not match:
                    drifts.append(
                        DriftItem(
                            invariant_key=inv_key,
                            doc_value=doc_val,
                            code_value=code_val,
                            file_path=src_file,
                            symbol_name=sym_name,
                            line_number=lineno,
                        )
                    )

    return drifts

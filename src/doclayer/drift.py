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


def _parse_raw_literal(raw: str) -> Any:
    """Parses primitive literal values from raw code tokens (TS, JS, Go, Rust)."""
    raw = raw.strip().rstrip(";,")
    if not raw:
        return None

    # Strip trailing comments if any
    if "//" in raw:
        slash_idx = raw.find("//")
        quote_d = raw.find('"')
        quote_s = raw.find("'")
        if (quote_d == -1 or slash_idx < quote_d) and (quote_s == -1 or slash_idx < quote_s):
            raw = raw[:slash_idx].strip()
        else:
            parts = raw.split("//")
            if len(parts) > 1 and not (raw.startswith('"') and raw.endswith('"')):
                raw = parts[0].strip()

    raw = raw.rstrip(";, ")

    # Booleans
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    if raw.lower() in ("null", "nil", "none"):
        return None

    # Strings: "...", '...', `...`
    if len(raw) >= 2 and (
        (raw.startswith('"') and raw.endswith('"')) or
        (raw.startswith("'") and raw.endswith("'")) or
        (raw.startswith("`") and raw.endswith("`"))
    ):
        return raw[1:-1]

    # Rust type suffixes (e.g. 5000_u64, 50u32, 100_i32) & numeric underscores
    cleaned_num = re.sub(r"_(i8|i16|i32|i64|i128|isize|u8|u16|u32|u64|u128|usize|f32|f64)$", "", raw)
    cleaned_num = re.sub(r"(i8|i16|i32|i64|i128|isize|u8|u16|u32|u64|u128|usize|f32|f64)$", "", cleaned_num)
    no_underscores = cleaned_num.replace("_", "")

    # Try Integer
    try:
        if no_underscores.startswith(("0x", "0X")):
            return int(no_underscores, 16)
        if no_underscores.startswith(("0o", "0O")):
            return int(no_underscores, 8)
        if no_underscores.startswith(("0b", "0B")):
            return int(no_underscores, 2)
        return int(no_underscores)
    except ValueError:
        pass

    # Try Float
    try:
        return float(no_underscores)
    except ValueError:
        pass

    # Arrays / Lists: [ ... ]
    if raw.startswith("[") and raw.endswith("]"):
        try:
            return ast.literal_eval(raw)
        except Exception:
            inner = raw[1:-1].strip()
            if not inner:
                return []
            items = [_parse_raw_literal(p) for p in inner.split(",")]
            return [it for it in items if it is not None]

    return None


def _register_constant(constants: Dict[str, Tuple[Any, str, int]], sym_name: str, val: Any, lineno: int) -> None:
    """Registers constant under multiple normalized keys for resilient fuzzy matching."""
    constants[sym_name.lower()] = (val, sym_name, lineno)
    norm = _normalize_key(sym_name)
    constants[norm] = (val, sym_name, lineno)
    no_under = sym_name.lower().replace("_", "")
    constants[no_under] = (val, sym_name, lineno)
    if no_under.startswith("max"):
        constants[no_under[3:]] = (val, sym_name, lineno)


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
                        _register_constant(constants, sym_name, val, node.lineno)

    return constants


def extract_constants_from_ts_js_file(file_path: Path) -> Dict[str, Tuple[Any, str, int]]:
    """
    Parses TypeScript/JavaScript files (.ts, .tsx, .js, .jsx) using pure standard library regex
    to extract exported and top-level constants.
    """
    if not file_path.exists():
        return {}

    try:
        content = file_path.read_text(encoding="utf-8-sig")
    except Exception:
        return {}

    constants: Dict[str, Tuple[Any, str, int]] = {}
    pattern = re.compile(r"^(?:export\s+)?const\s+([A-Za-z0-9_]+)(?:\s*:\s*[^=]+)?\s*=\s*(.+)$")

    for lineno, line in enumerate(content.splitlines(), start=1):
        line_clean = line.strip()
        match = pattern.match(line_clean)
        if match:
            sym_name = match.group(1)
            raw_val = match.group(2)
            val = _parse_raw_literal(raw_val)
            if val is not None:
                _register_constant(constants, sym_name, val, lineno)

    return constants


def extract_constants_from_go_file(file_path: Path) -> Dict[str, Tuple[Any, str, int]]:
    """
    Parses Go files (.go) using pure standard library regex to extract
    single-line and grouped const declarations.
    """
    if not file_path.exists():
        return {}

    try:
        content = file_path.read_text(encoding="utf-8-sig")
    except Exception:
        return {}

    constants: Dict[str, Tuple[Any, str, int]] = {}
    in_const_block = False

    single_pattern = re.compile(r"^\s*const\s+([A-Za-z0-9_]+)(?:\s+[a-zA-Z0-9_\[\]\*\.]+)?\s*=\s*(.+)$")
    block_pattern = re.compile(r"^\s*([A-Za-z0-9_]+)(?:\s+[a-zA-Z0-9_\[\]\*\.]+)?\s*=\s*(.+)$")

    for lineno, line in enumerate(content.splitlines(), start=1):
        line_clean = line.strip()
        if not line_clean or line_clean.startswith("//"):
            continue

        if line_clean.startswith("const (") or line_clean == "const (":
            in_const_block = True
            continue
        elif in_const_block and line_clean == ")":
            in_const_block = False
            continue

        if in_const_block:
            m = block_pattern.match(line_clean)
            if m:
                sym_name = m.group(1)
                val = _parse_raw_literal(m.group(2))
                if val is not None:
                    _register_constant(constants, sym_name, val, lineno)
        else:
            m = single_pattern.match(line_clean)
            if m:
                sym_name = m.group(1)
                val = _parse_raw_literal(m.group(2))
                if val is not None:
                    _register_constant(constants, sym_name, val, lineno)

    return constants


def extract_constants_from_rust_file(file_path: Path) -> Dict[str, Tuple[Any, str, int]]:
    """
    Parses Rust files (.rs) using pure standard library regex to extract
    pub const and const declarations.
    """
    if not file_path.exists():
        return {}

    try:
        content = file_path.read_text(encoding="utf-8-sig")
    except Exception:
        return {}

    constants: Dict[str, Tuple[Any, str, int]] = {}
    pattern = re.compile(r"^\s*(?:pub(?:\([^)]+\))?\s+)?const\s+([A-Za-z0-9_]+)\s*:\s*[^=]+\s*=\s*(.+)$")

    for lineno, line in enumerate(content.splitlines(), start=1):
        line_clean = line.strip()
        if not line_clean or line_clean.startswith("//"):
            continue
        m = pattern.match(line_clean)
        if m:
            sym_name = m.group(1)
            val = _parse_raw_literal(m.group(2))
            if val is not None:
                _register_constant(constants, sym_name, val, lineno)

    return constants


def extract_constants_from_file(file_path: Path) -> Dict[str, Tuple[Any, str, int]]:
    """
    Universal Polyglot Constant Extractor (Pure Python Standard Library).
    Extracts top-level constants across Python (.py), TypeScript (.ts, .tsx),
    JavaScript (.js, .jsx, .mjs, .cjs), Go (.go), and Rust (.rs).
    Returns: {normalized_key: (value, raw_symbol_name, line_number)}
    """
    if not file_path.exists():
        return {}

    suffix = file_path.suffix.lower()
    if suffix == ".py":
        return extract_constants_from_python_file(file_path)
    elif suffix in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
        return extract_constants_from_ts_js_file(file_path)
    elif suffix == ".go":
        return extract_constants_from_go_file(file_path)
    elif suffix == ".rs":
        return extract_constants_from_rust_file(file_path)
    return {}


def _ast_value_to_literal(node: ast.AST) -> Any:
    """Safely converts basic AST literal nodes to Python primitives."""
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, (ast.List, ast.Tuple)):
        return [_ast_value_to_literal(elt) for elt in node.elts]
    elif isinstance(node, ast.Set):
        return sorted([_ast_value_to_literal(elt) for elt in node.elts if _ast_value_to_literal(elt) is not None])
    return None


def _add_flattened_invariant(d: Dict[str, Any], key: str, val: Any) -> None:
    d[key.lower()] = val
    norm = _normalize_key(key)
    d[norm] = val
    no_under = key.lower().replace("_", "")
    d[no_under] = val
    if no_under.startswith("max"):
        d[no_under[3:]] = val


def detect_invariant_drift(
    invariants_data: Dict[str, Any],
    source_files: List[Path],
) -> List[DriftItem]:
    """
    Scans source files across all supported languages (Python, TypeScript, JavaScript, Go, Rust)
    and compares extracted code constants against doc invariants.
    """
    drifts: List[DriftItem] = []
    if not invariants_data or not isinstance(invariants_data, dict):
        return drifts

    flattened_invariants: Dict[str, Any] = {}
    for k, v in invariants_data.items():
        if isinstance(v, dict):
            for sub_k, sub_v in v.items():
                if isinstance(sub_v, dict) and "value" in sub_v:
                    val = sub_v["value"]
                else:
                    val = sub_v
                _add_flattened_invariant(flattened_invariants, sub_k, val)
        else:
            _add_flattened_invariant(flattened_invariants, k, v)

    for src_file in source_files:
        code_constants = extract_constants_from_file(src_file)
        seen_symbols: set = set()

        for inv_key, doc_val in flattened_invariants.items():
            if inv_key in code_constants:
                code_val, sym_name, lineno = code_constants[inv_key]
                if sym_name in seen_symbols:
                    continue

                # Compare values (handle list/tuple comparisons)
                if isinstance(doc_val, (list, tuple)) and isinstance(code_val, (list, tuple)):
                    match = sorted(list(doc_val)) == sorted(list(code_val))
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
                seen_symbols.add(sym_name)

    return drifts

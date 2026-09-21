"""
Polyglot AST Call-Flow Tracing and Behavioral Pipeline Synthesis for DocLayer.
Extracts module entrypoints, call graphs, data transformations, and state mutations
with zero external dependencies (Python ast + polyglot regex).
"""
import ast
from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class PipelineContract:
    function_name: str
    inputs: str
    transformation: str
    output_state: str
    evidence_anchor: str


@dataclass
class CallFlowSummary:
    entry_points: List[str] = field(default_factory=list)
    processing_nodes: List[str] = field(default_factory=list)
    storage_or_sinks: List[str] = field(default_factory=list)
    ascii_diagram: str = ""
    pipelines: List[PipelineContract] = field(default_factory=list)


def _clean_docstring(doc: Optional[str]) -> str:
    """Extracts first line/sentence of a docstring."""
    if not doc:
        return ""
    lines = [l.strip() for l in doc.strip().splitlines() if l.strip()]
    if not lines:
        return ""
    first = lines[0]
    # Remove trailing periods if chained
    return re.sub(r"\s+", " ", first).strip()


def _format_py_args(args_node: ast.arguments) -> str:
    """Formats AST arguments into concise parameter string."""
    params: List[str] = []
    # positional & keyword args
    for arg in args_node.args:
        if arg.arg in ("self", "cls"):
            continue
        ann = ""
        if arg.annotation:
            try:
                ann = f": {ast.unparse(arg.annotation)}"
            except Exception:
                pass
        params.append(f"{arg.arg}{ann}")
    if args_node.vararg:
        params.append(f"*{args_node.vararg.arg}")
    if args_node.kwarg:
        params.append(f"**{args_node.kwarg.arg}")
    return f"({', '.join(params)})"


def _analyze_function_effects(node: ast.AST) -> Tuple[str, str]:
    """
    Inspects AST body of a function to infer business logic and state mutations.
    Returns: (transformation_summary, output_or_state_mutation)
    """
    has_db = False
    has_file_write = False
    has_http = False
    has_calc = False
    has_dict_mutate = False
    return_exprs: List[str] = []

    for child in ast.walk(node):
        # Calls
        if isinstance(child, ast.Call):
            call_name = ""
            if isinstance(child.func, ast.Name):
                call_name = child.func.id.lower()
            elif isinstance(child.func, ast.Attribute):
                call_name = child.func.attr.lower()

            if any(k in call_name for k in ("sqlite", "execute", "cursor", "commit", "db", "query", "fetch")):
                has_db = True
            if any(k in call_name for k in ("write", "dump", "save", "flush", "to_csv", "to_sql", "to_json")):
                has_file_write = True
            if any(k in call_name for k in ("get", "post", "put", "request", "fetch", "urlopen", "curl")):
                has_http = True
            if any(k in call_name for k in ("calculate", "compute", "rebalance", "score", "evaluate", "sum", "round")):
                has_calc = True

        # Binary math ops
        if isinstance(child, (ast.BinOp, ast.Compare)):
            has_calc = True

        # Returns
        if isinstance(child, ast.Return) and child.value:
            try:
                unp = ast.unparse(child.value)
                if len(unp) < 40:
                    return_exprs.append(unp)
            except Exception:
                pass

    transform_parts: List[str] = []
    if has_http:
        transform_parts.append("Fetches remote payloads")
    if has_calc:
        transform_parts.append("Executes business math / calculations")
    if has_db:
        transform_parts.append("Queries / mutates database records")
    if has_file_write:
        transform_parts.append("Serializes structured output")

    trans_str = ", ".join(transform_parts) if transform_parts else "Processes domain logic"

    mutation_parts: List[str] = []
    if has_db:
        mutation_parts.append("Persists database state")
    if has_file_write:
        mutation_parts.append("Writes output artifact to disk")
    if return_exprs:
        mutation_parts.append(f"Returns `{return_exprs[0]}`")
    elif not mutation_parts:
        mutation_parts.append("Returns computed result")

    mut_str = "; ".join(mutation_parts)
    return trans_str, mut_str


def analyze_python_files(files: List[Path], repo_root: Path) -> CallFlowSummary:
    """Analyzes a collection of Python files to extract call sequences and pipeline contracts."""
    entry_points: List[str] = []
    processing_nodes: List[str] = []
    storage_sinks: List[str] = []
    pipelines: List[PipelineContract] = []

    seen_funcs: Set[str] = set()

    for file_path in files:
        if not file_path.exists() or file_path.suffix != ".py":
            continue
        try:
            content = file_path.read_text(encoding="utf-8-sig")
            tree = ast.parse(content, filename=str(file_path))
        except Exception:
            continue

        rel_path = file_path.relative_to(repo_root).as_posix() if repo_root in file_path.parents or file_path == repo_root else file_path.name
        stem = file_path.stem.lower()

        is_entry = stem in ("main", "server", "app", "cli", "launcher", "entrypoint") or "router" in stem
        is_storage = stem in ("storage", "db", "database", "repository", "models", "schema")

        if is_entry:
            entry_points.append(f"{file_path.name} (Entrypoint)")
        elif is_storage:
            storage_sinks.append(f"{file_path.name} (Persistence)")
        else:
            processing_nodes.append(f"{file_path.name} (Engine)")

        # Walk top-level functions and class methods
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fname = node.name
                if fname.startswith("_") and not fname.startswith("__init__"):
                    continue
                if fname in seen_funcs:
                    continue
                seen_funcs.add(fname)

                doc = ast.get_docstring(node)
                doc_clean = _clean_docstring(doc)
                inputs_sig = _format_py_args(node.args)
                auto_trans, auto_mut = _analyze_function_effects(node)

                final_trans = doc_clean or auto_trans
                anchor = f"{rel_path}::{fname}"

                pipelines.append(
                    PipelineContract(
                        function_name=f"`{fname}{inputs_sig}`",
                        inputs=f"Arguments: `{inputs_sig}`" if inputs_sig != "()" else "None / Environment",
                        transformation=final_trans,
                        output_state=auto_mut,
                        evidence_anchor=f"`{anchor}`",
                    )
                )

    # Deduplicate node lists
    entry_points = list(dict.fromkeys(entry_points))
    processing_nodes = list(dict.fromkeys(processing_nodes))
    storage_sinks = list(dict.fromkeys(storage_sinks))

    # Generate ASCII diagram
    e_str = entry_points[0] if entry_points else "Client / CLI / API Caller"
    p_str = processing_nodes[0] if processing_nodes else "Core Engine"
    s_str = storage_sinks[0] if storage_sinks else "Storage / DB / Disk Sinks"

    diagram = _render_ascii_callflow(e_str, p_str, s_str, processing_nodes[1:3])

    return CallFlowSummary(
        entry_points=entry_points,
        processing_nodes=processing_nodes,
        storage_or_sinks=storage_sinks,
        ascii_diagram=diagram,
        pipelines=pipelines,
    )


def _render_ascii_callflow(entry: str, engine: str, sink: str, extra_engines: List[str]) -> str:
    """Renders a clean, structured ASCII topology diagram."""
    lines = [
        f"[{entry}]",
        "        │",
        "        ▼",
        f"[{engine}]",
    ]
    if extra_engines:
        for ext in extra_engines:
            lines.extend([
                "        │",
                f"        ├──► [{ext}]",
            ])
    lines.extend([
        "        │",
        "        ▼",
        f"[{sink}]",
    ])
    return "\n".join(lines)


def analyze_polyglot_files(files: List[Path], repo_root: Path) -> CallFlowSummary:
    """Polyglot dispatcher for extracting call sequences and pipeline contracts across languages."""
    py_files = [f for f in files if f.suffix == ".py"]
    if py_files:
        return analyze_python_files(py_files, repo_root)

    # TS/JS/Go/Rust regex extraction
    entry_points: List[str] = []
    processing_nodes: List[str] = []
    storage_sinks: List[str] = []
    pipelines: List[PipelineContract] = []
    seen_funcs: Set[str] = set()

    fn_patterns = [
        # TS / JS: export function foo(x, y): T, const foo = (x) => ...
        re.compile(r"^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)", re.MULTILINE),
        re.compile(r"^(?:export\s+)?const\s+([A-Za-z0-9_]+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*(?::\s*[^=]+)?\s*=>", re.MULTILINE),
        # Go: func Foo(x int) (y string, err error)
        re.compile(r"^func\s+(?:\([^)]+\)\s+)?([A-Za-z0-9_]+)\s*\(([^)]*)\)", re.MULTILINE),
        # Rust: pub fn foo(x: &str) -> Result<...>
        re.compile(r"^(?:pub\s+)?(?:async\s+)?fn\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)", re.MULTILINE),
    ]

    for file_path in files:
        rel_path = file_path.relative_to(repo_root).as_posix() if repo_root in file_path.parents or file_path == repo_root else file_path.name
        stem = file_path.stem.lower()

        if stem in ("index", "main", "server", "app", "handler", "router", "cli"):
            entry_points.append(f"{file_path.name} (Entrypoint)")
        elif stem in ("db", "database", "storage", "repository", "store", "model"):
            storage_sinks.append(f"{file_path.name} (Persistence)")
        else:
            processing_nodes.append(f"{file_path.name} (Service/Module)")

        try:
            content = file_path.read_text(encoding="utf-8-sig")
        except Exception:
            continue

        for pat in fn_patterns:
            for match in pat.finditer(content):
                fname = match.group(1)
                args_raw = match.group(2).strip()
                if fname.startswith("_") or fname in seen_funcs:
                    continue
                seen_funcs.add(fname)
                anchor = f"{rel_path}::{fname}"
                inputs_str = f"({args_raw})" if args_raw else "()"
                pipelines.append(
                    PipelineContract(
                        function_name=f"`{fname}{inputs_str}`",
                        inputs=f"Arguments: `{inputs_str}`" if inputs_str != "()" else "None / Environment",
                        transformation="Processes business contract logic",
                        output_state="Returns computed value / mutates state",
                        evidence_anchor=f"`{anchor}`",
                    )
                )

    e_str = entry_points[0] if entry_points else "Client / API Caller"
    p_str = processing_nodes[0] if processing_nodes else "Core Service Engine"
    s_str = storage_sinks[0] if storage_sinks else "Storage & Dependencies"
    diagram = _render_ascii_callflow(e_str, p_str, s_str, processing_nodes[1:3])

    return CallFlowSummary(
        entry_points=list(dict.fromkeys(entry_points)),
        processing_nodes=list(dict.fromkeys(processing_nodes)),
        storage_or_sinks=list(dict.fromkeys(storage_sinks)),
        ascii_diagram=diagram,
        pipelines=pipelines,
    )

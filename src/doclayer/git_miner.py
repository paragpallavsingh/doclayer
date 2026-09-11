"""
Git Commit History and Post-Mortem Miner for doclayer.
Extracts institutional knowledge, constant genesis (git log -S),
and negative safety runbook invariants (reverts, incident fixes, CVEs)
from git repository history using standard library subprocess.
"""
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
from typing import Any, Dict, List, Optional, Tuple


COMMIT_DELIMITER = "---DOCLAYER_COMMIT_END---"
GIT_COMMAND_TIMEOUT_SECONDS = 10
MAX_MINED_COMMITS = 50

TICKET_PATTERNS = [
    re.compile(r"(INC-\d+)", re.IGNORECASE),
    re.compile(r"(CVE-\d{4}-\d+)", re.IGNORECASE),
    re.compile(r"(RFC-\d+)", re.IGNORECASE),
    re.compile(r"(ADR-\d+)", re.IGNORECASE),
    re.compile(r"(Fixes\s+#\d+)", re.IGNORECASE),
    re.compile(r"(#\d+)", re.IGNORECASE),
]


@dataclass
class CommitRecord:
    commit_hash: str
    short_hash: str
    author: str
    date: str
    subject: str
    body: str


@dataclass
class ConstantOrigin:
    symbol_name: str
    commit_hash: str
    short_hash: str
    author: str
    date: str
    subject: str
    rationale: str
    reference: str
    epistemic_status: str = "STATED"


@dataclass
class MinedNegativeInvariant:
    symptom: str
    probable_cause: str
    safe_remediation: str
    prohibited_actions: str
    reference: str
    commit_hash: str


def run_git_command(args: List[str], cwd: Path) -> Optional[str]:
    """Executes a git command safely using standard library subprocess."""
    try:
        res = subprocess.run(
            ["git"] + args,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GIT_COMMAND_TIMEOUT_SECONDS,
        )
        if res.returncode == 0:
            return res.stdout.strip()
        return None
    except (FileNotFoundError, subprocess.SubprocessError, PermissionError):
        return None


def is_git_repo(path: Path) -> bool:
    """Checks if target directory is within a valid git repository."""
    out = run_git_command(["rev-parse", "--is-inside-work-tree"], cwd=path)
    return out == "true"


def get_repo_root(path: Path) -> Path:
    """Finds the root directory of the git repository."""
    out = run_git_command(["rev-parse", "--show-toplevel"], cwd=path)
    if out:
        return Path(out)
    return path.resolve()


def parse_commits(raw_output: str) -> List[CommitRecord]:
    """Parses raw git log output with COMMIT_DELIMITER into CommitRecords."""
    if not raw_output:
        return []

    records: List[CommitRecord] = []
    chunks = raw_output.split(COMMIT_DELIMITER)

    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue

        lines = chunk.splitlines()
        header = lines[0]
        parts = header.split("|")
        if len(parts) < 5:
            continue

        c_hash = parts[0].strip()
        s_hash = parts[1].strip()
        author = parts[2].strip()
        date = parts[3].strip()
        subject = parts[4].strip()
        body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""

        records.append(
            CommitRecord(
                commit_hash=c_hash,
                short_hash=s_hash,
                author=author,
                date=date,
                subject=subject,
                body=body,
            )
        )
    return records


def extract_ticket_or_reference(text: str, fallback_hash: str) -> str:
    """Extracts formal issue/ADR/incident ticket or falls back to commit short hash."""
    for pat in TICKET_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(1).upper()
    return f"Commit: {fallback_hash}"


def _clean_rationale(subject: str, body: str) -> str:
    """Derives a concise, high-signal 1-line rationale from commit message."""
    clean_subj = re.sub(r"^(?:feat|fix|perf|chore|refactor|docs|build|ci)(?:\([^)]+\))?:\s*", "", subject, flags=re.IGNORECASE)
    clean_subj = clean_subj.strip()

    # Look for explicit "why" or "because" in body
    if body:
        for line in body.splitlines():
            line_s = line.strip()
            if any(line_s.lower().startswith(prefix) for prefix in ("why:", "reason:", "rationale:", "to prevent", "in order to")):
                return re.sub(r"^(?:why|reason|rationale):\s*", "", line_s, flags=re.IGNORECASE).strip()

    return clean_subj or "Configured baseline system constraint"


def mine_constant_origin(
    symbol_name: str,
    file_path: Optional[Path] = None,
    repo_path: Optional[Path] = None,
) -> Optional[ConstantOrigin]:
    """
    Uses `git log -S <symbol_name>` to find the genesis or modification commit
    for a given constant symbol. Extracts author rationale and references.
    """
    target_dir = repo_path or (file_path.parent if file_path else Path.cwd())
    if not is_git_repo(target_dir):
        return None

    cmd_args = [
        "log",
        f"-S{symbol_name}",
        "-n", "5",
        f"--format=%H|%h|%an|%ad|%s%n%b%n{COMMIT_DELIMITER}",
        "--date=short",
    ]
    if file_path and file_path.exists():
        rel_path = file_path.as_posix()
        cmd_args.extend(["--", rel_path])

    out = run_git_command(cmd_args, cwd=target_dir)
    if not out and file_path:
        # Retry across whole repo if file was moved or renamed
        out = run_git_command(cmd_args[:-2], cwd=target_dir)

    if not out:
        return None

    commits = parse_commits(out)
    if not commits:
        return None

    # Pick the most relevant commit (first one returned by git log)
    primary = commits[0]
    rationale = _clean_rationale(primary.subject, primary.body)
    ref = extract_ticket_or_reference(f"{primary.subject}\n{primary.body}", primary.short_hash)

    return ConstantOrigin(
        symbol_name=symbol_name,
        commit_hash=primary.commit_hash,
        short_hash=primary.short_hash,
        author=primary.author,
        date=primary.date,
        subject=primary.subject,
        rationale=rationale,
        reference=ref,
        epistemic_status="STATED",
    )


def mine_negative_runbooks(
    repo_path: Path,
    path_filter: Optional[Path] = None,
    max_commits: int = MAX_MINED_COMMITS,
) -> List[MinedNegativeInvariant]:
    """
    Mines repository git history for past incidents, bug fixes, and reverts.
    Populates agent safety runbooks with prohibited destructive actions.
    """
    if not is_git_repo(repo_path):
        return []

    cmd_args = [
        "log",
        f"-n", str(max_commits),
        f"--format=%H|%h|%an|%ad|%s%n%b%n{COMMIT_DELIMITER}",
        "--date=short",
    ]
    if path_filter:
        cmd_args.extend(["--", path_filter.as_posix()])

    out = run_git_command(cmd_args, cwd=repo_path)
    if not out:
        return []

    commits = parse_commits(out)
    runbooks: List[MinedNegativeInvariant] = []
    seen_hashes = set()

    incident_keywords = (
        "revert", "revert:", "revert \"",
        "fix:", "fix(", "hotfix", "bug", "patch:",
        "cve-", "inc-", "incident", "outage", "deadlock", "leak", "panic"
    )

    for commit in commits:
        if commit.short_hash in seen_hashes:
            continue

        subj_lower = commit.subject.lower()
        body_lower = commit.body.lower()
        full_text = f"{subj_lower}\n{body_lower}"

        if not any(kw in full_text for kw in incident_keywords):
            continue

        ref = extract_ticket_or_reference(f"{commit.subject}\n{commit.body}", commit.short_hash)

        # 1. Revert Commits: What was reverted was the prohibited action
        if "revert" in subj_lower:
            # Extract what was reverted
            m = re.search(r"revert\s+[\"']?([^\"'\n]+)[\"']?", commit.subject, re.IGNORECASE)
            reverted_item = m.group(1) if m else commit.subject
            symptom = f"Instability or regression caused by: {reverted_item.strip()}"
            cause = f"Reverted commit broke invariants or introduced unhandled failure modes ({commit.short_hash})"
            safe_action = "Maintain stable configuration and verify behavior in staging before reapplying changes"
            prohibited = f"NEVER re-apply '{reverted_item.strip()}' without comprehensive regression tests"
        else:
            # 2. Bug fixes and incident post-mortems
            clean_title = re.sub(r"^(?:fix|hotfix|patch)(?:\([^)]+\))?:\s*", "", commit.subject, flags=re.IGNORECASE).strip()
            symptom = f"Defect or unexpected failure: {clean_title}"
            cause = "Edge case or invalid parameter handling resolved in historical commit"
            safe_action = f"Apply fix from {commit.short_hash}: {clean_title}"
            prohibited = f"NEVER bypass regression guards for: {clean_title}"

        runbooks.append(
            MinedNegativeInvariant(
                symptom=symptom,
                probable_cause=cause,
                safe_remediation=safe_action,
                prohibited_actions=prohibited,
                reference=ref,
                commit_hash=commit.commit_hash,
            )
        )
        seen_hashes.add(commit.short_hash)

    return runbooks


@dataclass
class SubsystemDiscovery:
    name: str
    slug: str
    package_path: str
    language: str
    source_files: List[Path]
    primary_owner: str
    constants: Dict[str, Tuple[Any, str, int]]
    constant_origins: Dict[str, ConstantOrigin]
    mined_runbooks: List[MinedNegativeInvariant]


def discover_subsystems(repo_path: Path) -> List[SubsystemDiscovery]:
    """
    Scans a repository to discover candidate software subsystems,
    extracts code constants, queries git history for origins and post-mortems.
    """
    repo_root = get_repo_root(repo_path)
    subsystems: List[SubsystemDiscovery] = []

    # Directories to ignore
    ignore_dirs = {
        ".git", ".github", ".doclayer", ".venv", "venv", "node_modules",
        "dist", "build", "__pycache__", "target", "vendor", ".agents",
        "tests", "test", "docs", "assets"
    }

    # Discover candidate directories
    candidate_dirs: List[Path] = []

    # Check src/ or pkg/ or services/ or modules/
    for top_container in ("src", "pkg", "services", "modules", "internal", "packages"):
        top_p = repo_root / top_container
        if top_p.is_dir():
            for child in top_p.iterdir():
                if child.is_dir() and child.name not in ignore_dirs:
                    candidate_dirs.append(child)

    # If none found, inspect direct children of repo root
    if not candidate_dirs:
        for child in repo_root.iterdir():
            if child.is_dir() and child.name not in ignore_dirs and not child.name.startswith("."):
                candidate_dirs.append(child)

    from doclayer.drift import extract_constants_from_file

    valid_exts = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".rs"}

    for c_dir in candidate_dirs:
        # Collect source files
        sources = [f for f in c_dir.glob("**/*") if f.is_file() and f.suffix.lower() in valid_exts]
        if not sources:
            continue

        # Language detection
        ext_counts: Dict[str, int] = {}
        for s in sources:
            ext_counts[s.suffix.lower()] = ext_counts.get(s.suffix.lower(), 0) + 1
        top_ext = max(ext_counts, key=ext_counts.get)
        lang_map = {
            ".py": "python",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "javascript",
            ".jsx": "javascript",
            ".go": "go",
            ".rs": "rust",
        }
        detected_lang = lang_map.get(top_ext, "polyglot")

        # Extract constants across files
        all_constants: Dict[str, Tuple[Any, str, int]] = {}
        constant_origins: Dict[str, ConstantOrigin] = {}
        for s_file in sources:
            file_consts = extract_constants_from_file(s_file)
            for k, (val, raw_sym, lineno) in file_consts.items():
                if k not in all_constants:
                    all_constants[k] = (val, raw_sym, lineno)

        # Ground extracted constants using Git History Miner
        for k, (val, raw_sym, lineno) in list(all_constants.items())[:15]:
            origin = mine_constant_origin(raw_sym, repo_path=repo_root)
            if origin:
                constant_origins[k] = origin

        # Mine negative runbooks from commit history touching this subsystem
        runbooks = mine_negative_runbooks(repo_root, path_filter=c_dir.relative_to(repo_root), max_commits=20)

        # Deduce owner from git log
        owner_str = "@engineering-team"
        author_out = run_git_command(["log", "-n", "10", "--format=%an", "--", c_dir.relative_to(repo_root).as_posix()], cwd=repo_root)
        if author_out:
            top_author = author_out.splitlines()[0].strip().replace(" ", "-").lower()
            owner_str = f"@{top_author}"

        slug = c_dir.name.lower().replace("_", "-")
        rel_pkg = c_dir.relative_to(repo_root).as_posix() + "/"

        subsystems.append(
            SubsystemDiscovery(
                name=c_dir.name.replace("-", " ").replace("_", " ").title(),
                slug=slug,
                package_path=rel_pkg,
                language=detected_lang,
                source_files=sources,
                primary_owner=owner_str,
                constants=all_constants,
                constant_origins=constant_origins,
                mined_runbooks=runbooks,
            )
        )

    return subsystems

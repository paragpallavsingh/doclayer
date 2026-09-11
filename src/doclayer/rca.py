"""
RCA (Root Cause Analysis) and Post-Mortem Injector for doclayer.
Safely mutates subsystem layer Markdown files with durable architectural decisions,
invariants, and operational/agent safety runbook additions.
"""
from pathlib import Path
import re
from typing import List, Optional, Tuple


def _find_section_bounds(content: str, keywords: List[str]) -> Optional[Tuple[int, int]]:
    """Locates start and end byte offsets of a section by title keyword match."""
    sec_header_pattern = re.compile(r"^##\s+(?:\d+\.\s+)?(.*)$", re.MULTILINE)
    matches = list(sec_header_pattern.finditer(content))

    for idx, match in enumerate(matches):
        title = match.group(1).lower()
        if any(kw.lower() in title for kw in keywords):
            sec_start = match.end()
            sec_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
            return (sec_start, sec_end)
    return None


def append_table_row_to_section(content: str, keywords: List[str], new_row: str) -> str:
    """
    Appends a new markdown table row to the table within the designated section matching keywords.
    """
    bounds = _find_section_bounds(content, keywords)
    if not bounds:
        # Fallback: append row at end of document if section not found
        return content.rstrip() + f"\n\n{new_row}\n"

    sec_start, sec_end = bounds
    section_text = content[sec_start:sec_end]
    lines = section_text.splitlines()

    # Find the last table row line starting with '|'
    last_table_line_idx = -1
    for idx, line in enumerate(lines):
        if line.strip().startswith("|"):
            last_table_line_idx = idx

    if last_table_line_idx != -1:
        lines.insert(last_table_line_idx + 1, new_row)
        new_sec_text = "\n".join(lines)
    else:
        new_sec_text = section_text.rstrip() + f"\n\n{new_row}\n\n"

    return content[:sec_start] + new_sec_text + content[sec_end:]


def update_invariants_fence(content: str, key_path: str, value_str: str) -> str:
    """
    Updates or inserts a key/value inside the ```invariants code fence.
    """
    fence_pattern = re.compile(r"(```(?:invariants|toml)\s*\n)(.*?)(```)", re.DOTALL | re.IGNORECASE)
    match = fence_pattern.search(content)
    if not match:
        return content

    header = match.group(1)
    fence_body = match.group(2)
    footer = match.group(3)

    # If key_path has dot (e.g. invariants.timeout_ms or timeout_ms)
    parts = key_path.split(".", 1)
    if len(parts) == 2:
        section_name, key_name = parts[0].strip(), parts[1].strip()
        sec_header = f"[{section_name}]"
        if sec_header in fence_body:
            key_regex = re.compile(rf"({re.escape(sec_header)}.*?)({re.escape(key_name)}\s*=\s*.*?)(\n\s*\[|\n\s*```|$)", re.DOTALL)
            if key_regex.search(fence_body):
                def replace_key(m):
                    prefix = m.group(1)
                    suffix = m.group(3)
                    return f"{prefix}{key_name} = {value_str}{suffix}"
                fence_body = key_regex.sub(replace_key, fence_body)
            else:
                fence_body = fence_body.replace(sec_header, f"{sec_header}\n{key_name} = {value_str}")
        else:
            fence_body = fence_body.rstrip() + f"\n\n[{section_name}]\n{key_name} = {value_str}\n"
    else:
        key_name = parts[0].strip()
        key_regex = re.compile(rf"^{re.escape(key_name)}\s*=\s*.*$", re.MULTILINE)
        if key_regex.search(fence_body):
            fence_body = key_regex.sub(f"{key_name} = {value_str}", fence_body)
        else:
            fence_body = fence_body.rstrip() + f"\n{key_name} = {value_str}\n"

    return content[:match.start()] + header + fence_body.rstrip() + "\n" + footer + content[match.end():]


def inject_rca_record(
    file_path: Path,
    incident_id: str,
    decision: str,
    rationale: str,
    invariant_pair: Optional[str] = None,
    symptom: Optional[str] = None,
    remediation: Optional[str] = None,
    prohibited: Optional[str] = None,
    anchor: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Injects an RCA decision into Contracts/Decisions section, updates invariants, and adds agent safety runbook entries.
    """
    if not file_path.exists():
        return False, f"File not found: {file_path}"

    content = file_path.read_text(encoding="utf-8-sig")
    ref_formatted = f"`{incident_id}`" if not incident_id.startswith("`") else incident_id

    # 1. Update Invariants TOML fence if supplied
    updated_content = content
    if invariant_pair:
        if "=" in invariant_pair:
            k, v = invariant_pair.split("=", 1)
            updated_content = update_invariants_fence(updated_content, k.strip(), v.strip())
            
            # Also append to Section 2 Contracts table
            contract_key = k.strip().split(".")[-1]
            contract_row = f"| `{contract_key} = {v.strip()}` | {rationale} | {ref_formatted} | `{anchor or file_path.name}` |"
            try:
                updated_content = append_table_row_to_section(updated_content, ["Contract", "Invariant"], contract_row)
            except Exception:
                pass
        else:
            return False, f"Invalid invariant pair '{invariant_pair}', expected format 'key=value'"

    # 2. Append to Decisions table if separate section exists
    decisions_row = f"| **{decision}** | {rationale} | {ref_formatted} |"
    try:
        updated_content = append_table_row_to_section(updated_content, ["Decision", "Rationale"], decisions_row)
    except Exception:
        pass

    # 3. Handle Runbook addition if symptom & remediation provided
    if symptom and remediation:
        prohibited_clean = prohibited if prohibited else "None specified"
        # Check if runbook table has 5 columns (with Prohibited Actions) or 4 columns
        bounds = _find_section_bounds(updated_content, ["Failure", "Runbook", "Symptom"])
        if bounds:
            sec_text = updated_content[bounds[0]:bounds[1]]
            first_table_line = next((l for l in sec_text.splitlines() if l.strip().startswith("|")), "")
            has_prohibited_col = "prohibited" in first_table_line.lower() or "not to do" in first_table_line.lower()
            if has_prohibited_col:
                runbook_row = f"| `{symptom}` | {rationale} | {remediation} | {prohibited_clean} | {ref_formatted} |"
            else:
                runbook_row = f"| `{symptom}` | {rationale} | {remediation} | {ref_formatted} |"
        else:
            runbook_row = f"| `{symptom}` | {rationale} | {remediation} | {prohibited_clean} | {ref_formatted} |"

        try:
            updated_content = append_table_row_to_section(updated_content, ["Failure", "Runbook", "Symptom"], runbook_row)
        except Exception as e:
            return False, f"Failed to update Runbook section: {e}"

    # Write updated content
    file_path.write_text(updated_content, encoding="utf-8")
    return True, f"Successfully injected RCA record '{incident_id}' into {file_path.name}"

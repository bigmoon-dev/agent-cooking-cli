from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_expert_profile(expert_path: str | Path) -> dict[str, Any] | None:
    expert_dir = Path(expert_path).expanduser().resolve()
    profile_yaml = expert_dir / "output" / "profile.yaml"
    if not profile_yaml.exists():
        profile_yaml = expert_dir / "profile.yaml"
    if not profile_yaml.exists():
        return None
    with profile_yaml.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        return None
    return data


def extract_constraints(profile: dict[str, Any]) -> list[dict[str, str]]:
    constraints: list[dict[str, str]] = []
    sections = profile.get("sections")
    if not isinstance(sections, dict):
        return constraints
    for section_key, items in sections.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            key = item.get("key", "")
            value = item.get("value", "")
            if key and value:
                constraints.append({
                    "section": section_key,
                    "key": key,
                    "value": value,
                })
    return constraints


def generate_claude_md(
    profile_id: str,
    description: str,
    constraints: list[dict[str, str]],
    *,
    workspace_root: str | None = None,
) -> str:
    lines: list[str] = []

    lines.append("# CLAUDE.md")

    lines.append("")
    lines.append("This project uses `kitchen` (agent-cooking-cli) for evidence-driven workflow.")

    lines.append("")
    lines.append("## Workflow Profile")
    lines.append("")
    lines.append(f"- **Profile**: `{profile_id}`")
    if description:
        lines.append(f"- **Description**: {description}")

    lines.append("")
    lines.append("## Expert Constraints (from dianoia-distilled expert profile)")
    lines.append("")
    lines.append("The following domain expertise must guide every decision in this workflow.")
    lines.append("")

    current_section = ""
    for c in constraints:
        section_label = _section_label(c["section"])
        if section_label != current_section:
            current_section = section_label
            lines.append(f"### {section_label}")
            lines.append("")
        lines.append(f"- **{c['key']}**: {c['value']}")
        lines.append("")

    lines.append("")
    lines.append("## Golden Path")
    lines.append("")
    lines.append("```bash")
    lines.append(
        f"export TRIAGEFLOW_ROOT={workspace_root}"
        if workspace_root
        else "export TRIAGEFLOW_ROOT=$(pwd)"
    )
    lines.append("")
    lines.append("kitchen start --profile {profile_id}".format(profile_id=profile_id))
    lines.append("")
    lines.append("kitchen next")
    lines.append("```")

    lines.append("")
    lines.append("## Hard Rules")
    lines.append("")
    lines.append("- State must be persisted under `triage/`. Do not rely on chat memory.")
    lines.append("- No guessing: every hypothesis or direction MUST cite evidence IDs (E###).")
    lines.append("- Facts must not contain speculation words (possible, probably, should, might).")
    lines.append("- Use CLI commands over manual file edits in `triage/`: `facts add`, `hypotheses add`, `direction-build`, `validate`.")
    lines.append("- Before any action, run `kitchen next` to confirm the recommended next step.")
    lines.append("- After each change, run `kitchen validate` to verify rules.")
    lines.append("- **The expert constraints above are authoritative.** If your reasoning contradicts them, re-evaluate.")

    lines.append("")
    lines.append("## Minimal Commands")
    lines.append("")
    lines.append("- `kitchen status` — workflow digest")
    lines.append("- `kitchen next` — recommended next step")
    lines.append("- `kitchen validate` — rule check")

    return "\n".join(lines)


_SECTION_LABELS: dict[str, str] = {
    "identity": "Identity (Who the expert is)",
    "goals": "Goals (What the expert optimizes for)",
    "methods": "Methods (How the expert works)",
    "values": "Values (What the expert considers non-negotiable)",
    "knowledge_sources": "Knowledge Sources",
    "conditional_rules": "Conditional Rules",
    "priority_ordering": "Priority Ordering",
    "pragmatic_thresholds": "Pragmatic Thresholds",
}


def _section_label(key: str) -> str:
    return _SECTION_LABELS.get(key, key.replace("_", " ").title())

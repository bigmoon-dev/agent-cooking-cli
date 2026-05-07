from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

import typer

from .core import dump_yaml, write_text
from .expert import extract_constraints, generate_claude_md, load_expert_profile


def infer_triage_templates() -> dict[str, str]:
    # Keep templates minimal; agents fill them.
    return {
        "case.yaml": (
            "case_id: \"\"\n"
            "title: \"\"\n"
            "problem_description: |\n"
            "  \n"
            "code_paths: []\n"
            "log_paths: []\n"
            "work_done: |\n"
            "  \n"
            "excluded_doc_paths: []\n"
            "constraints:\n"
            "  - \"Every hypothesis must cite code or log evidence\"\n"
            "  - \"No imagination; evidence-first\"\n"
        ),
        "facts.md": (
            "# Facts\n\n"
            "Rules:\n"
            "- Facts only; avoid speculation wording.\n"
            "- Each fact cites evidence IDs like (E001).\n\n"
            "F001: \n"
        ),
        "hypotheses.md": (
            "# Hypotheses\n\n"
            "Rules:\n"
            "- Each hypothesis MUST cite at least one evidence ID (E###).\n"
            "- No evidence -> move to leads.md (does not participate in direction ranking).\n\n"
            "H001 (Status: Open | Confidence: Medium)\n"
            "Hypothesis: \n"
            "Evidence: ()\n"
            "Test: \n\n"
        ),
        "directions.md": (
            "# Directions\n\n"
            "Rules:\n"
            "- Keep top 1-3 directions only.\n"
            "- Each direction MUST cite evidence IDs (E###).\n\n"
            "DIR-1 (Confidence: Medium)\n"
            "Direction: \n"
            "Explains: (F001)\n"
            "Evidence chain: ()\n"
            "Next minimal test: \n"
            "Falsify if: \n\n"
        ),
        "experiments.md": (
            "# Experiments\n\n"
            "X001\n"
            "Goal: \n"
            "Steps:\n"
            "Expected:\n"
            "Observed:\n"
            "Evidence produced: (E001)\n"
            "Conclusion: \n\n"
        ),
        "excluded.md": (
            "# Excluded Suspects\n\n"
            "S001: \n"
            "Excluded because: (E001)\n"
            "Experiment: (X001)\n"
            "Residual risk: \n\n"
        ),
        "leads.md": (
            "# Leads (Not hypotheses)\n\n"
            "Only store leads that still have some evidence.\n\n"
        ),
        os.path.join("evidence", "index.md"): (
            "| Evidence ID | Type | Source | Time | What it shows (fact only) |\n"
            "|---|---|---|---|---|\n"
        ),
    }


def init_workspace(
    *,
    tdir: Path,
    force: bool,
    profile_id: str,
    load_profile_yaml_func: Callable[[str], dict],
    require_valid_profile_func: Callable[[dict], dict],
    expert_path: str = "",
    workspace_root: str = "",
) -> None:
    """Initialize triage/ workspace with templates."""

    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / "evidence" / "log").mkdir(parents=True, exist_ok=True)
    (tdir / "evidence" / "code").mkdir(parents=True, exist_ok=True)
    (tdir / "evidence" / "cmd").mkdir(parents=True, exist_ok=True)

    templates = infer_triage_templates()
    created = 0
    skipped = 0
    for rel, content in templates.items():
        path = tdir / rel
        if path.exists() and not force:
            skipped += 1
            continue
        write_text(path, content)
        created += 1

    profile_data: dict | None = None
    if profile_id.strip():
        profile_data = require_valid_profile_func(load_profile_yaml_func(profile_id.strip()))
        prof_path = tdir / "profile.yaml"
        if (not prof_path.exists()) or force:
            dump_yaml(prof_path, profile_data)
            typer.echo(f"Wrote {prof_path}")
        else:
            typer.echo(f"Skipped existing {prof_path} (use --force to overwrite)")

    claude_md_content: str | None = None
    if expert_path:
        if profile_data is None:
            typer.echo("Warning: --expert requires --profile to generate CLAUDE.md")
        else:
            expert = load_expert_profile(expert_path)
            if expert is not None:
                constraints = extract_constraints(expert)
                if not constraints:
                    typer.echo(f"Warning: no constraints found in expert profile at {expert_path}")
                else:
                    claude_md_content = generate_claude_md(
                        profile_id=profile_id.strip(),
                        description=profile_data.get("description", ""),
                        constraints=constraints,
                        workspace_root=workspace_root,
                    )
                    typer.echo(f"Loaded expert profile with {len(constraints)} constraints")
            else:
                typer.echo(f"Warning: no profile.yaml found in {expert_path}")

    claude_md_path = tdir.parent / "CLAUDE.md"
    if claude_md_content and ((not claude_md_path.exists()) or force):
        write_text(claude_md_path, claude_md_content)
        typer.echo(f"Wrote {claude_md_path}")
    elif claude_md_path.exists() and not force:
        typer.echo(f"Skipped existing {claude_md_path} (use --force to overwrite)")

    typer.echo(f"Initialized {tdir} (created={created}, skipped={skipped})")

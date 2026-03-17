from __future__ import annotations

import re
from pathlib import Path

import typer

from .core import load_yaml, read_text_if_exists


def print_status(tdir: Path) -> None:
    """Print a compact digest for agents (keeps context small)."""

    case = load_yaml(tdir / "case.yaml")
    title = case.get("title") or ""
    case_id = case.get("case_id") or ""

    index_text = read_text_if_exists(tdir / "evidence" / "index.md")
    eids = re.findall(r"\bE\d{3}\b", index_text)
    last_eids = list(dict.fromkeys(eids))[-5:]

    def _first_lines(path: Path, n: int) -> str:
        lines = read_text_if_exists(path).splitlines()
        return "\n".join(lines[:n]).strip()

    typer.echo(f"Case: {case_id} {title}")
    typer.echo(f"Triage dir: {tdir}")
    typer.echo(f"Evidence count: {len(set(eids))} (latest: {', '.join(last_eids) if last_eids else 'none'})")
    typer.echo("")
    typer.echo("Facts (top):")
    typer.echo(_first_lines(tdir / "facts.md", 12) or "(empty)")
    typer.echo("")
    typer.echo("Hypotheses (top):")
    typer.echo(_first_lines(tdir / "hypotheses.md", 18) or "(empty)")
    typer.echo("")
    typer.echo("Directions (top):")
    typer.echo(_first_lines(tdir / "directions.md", 18) or "(empty)")

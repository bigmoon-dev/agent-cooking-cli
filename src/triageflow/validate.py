from __future__ import annotations

import re
from pathlib import Path
from typing import List

import typer

from .core import emit, read_text_if_exists
from .validate_rules import evidence_files_on_disk, known_eids


def validate_workspace(tdir: Path) -> None:
    """Validate hard rules (evidence citations, no speculation in facts)."""

    known = known_eids(tdir)
    disk = set(evidence_files_on_disk(tdir).keys())

    errors: List[str] = []

    # Facts: ban speculation words
    facts_path = tdir / "facts.md"
    facts_text = read_text_if_exists(facts_path)
    banned = [
        # keep this list short; add more when needed
        "possible",
        "probably",
        "should",
        "might",
        "可能",
        "怀疑",
        "大概",
        "应该",
        "推测",
        "估计",
        "也许",
    ]
    for w in banned:
        # Use word-boundary for ASCII words; substring match for CJK
        if w.isascii():
            if re.search(rf"\b{re.escape(w)}\b", facts_text):
                errors.append(f"facts.md contains banned speculation word: {w}")
        else:
            if w in facts_text:
                errors.append(f"facts.md contains banned speculation word: {w}")

    # Facts: each non-empty F### line must cite an EID
    for line in facts_text.splitlines():
        m = re.match(r"^(F\d{3}):\s*(.*)$", line)
        if not m:
            continue
        payload = m.group(2).strip()
        if not payload:
            continue
        if not re.search(r"\bE\d{3}\b", payload):
            errors.append(f"facts.md fact '{m.group(1)}' cites no EID")

    # Hypotheses and directions: each heading block must cite at least one known EID
    def _check_blocks(path: Path, label: str, header_re: str) -> None:
        text = read_text_if_exists(path)
        if not text.strip():
            return

        # Split by headings that start at line start.
        lines = text.splitlines()
        cur_header = None
        cur_buf: List[str] = []
        blocks: list[tuple[str, str]] = []
        hpat = re.compile(header_re)
        for ln in lines:
            m = hpat.match(ln)
            if m:
                if cur_header is not None:
                    blocks.append((cur_header, "\n".join(cur_buf)))
                cur_header = m.group(0)
                cur_buf = [ln]
            else:
                if cur_header is not None:
                    cur_buf.append(ln)
        if cur_header is not None:
            blocks.append((cur_header, "\n".join(cur_buf)))

        for header, body in blocks:
            eids = set(re.findall(r"\bE\d{3}\b", body))
            if not eids and label in {"hypotheses.md", "directions.md"}:
                # Detect template blocks by empty content fields
                is_template = False
                if label == "hypotheses.md" and re.search(r"^Hypothesis:\s*$", body, re.MULTILINE):
                    is_template = True
                if label == "directions.md" and re.search(r"^Direction:\s*$", body, re.MULTILINE):
                    is_template = True
                if is_template:
                    continue
            if not eids:
                errors.append(f"{label}: block '{header}' cites no EID")
                continue
            unknown = sorted(eids - known)
            if unknown:
                errors.append(f"{label}: block '{header}' cites unknown EIDs: {', '.join(unknown)}")
            missing_files = sorted(eids - disk)
            if missing_files:
                errors.append(
                    f"{label}: block '{header}' references EIDs missing evidence files: {', '.join(missing_files)}"
                )

    _check_blocks(tdir / "hypotheses.md", "hypotheses.md", r"^H\d{3}\b.*")
    _check_blocks(tdir / "directions.md", "directions.md", r"^DIR-\d+\b.*")

    if errors:
        emit("validate.failed", tdir=tdir, errors=errors)
        for e in errors:
            typer.echo(f"ERROR: {e}")
        raise typer.Exit(code=2)

    emit("validate.passed", tdir=tdir)
    typer.echo("OK: validation passed")

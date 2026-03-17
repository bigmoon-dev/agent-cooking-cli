from __future__ import annotations

import re
from pathlib import Path
from typing import List

import typer

from .core import read_text_if_exists


def evidence_files_on_disk(triage_dir: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    ev_dir = triage_dir / "evidence"
    if not ev_dir.exists():
        return out
    for sub in ("log", "code", "cmd"):
        d = ev_dir / sub
        if not d.exists():
            continue
        for p in d.glob("E[0-9][0-9][0-9]_*.txt"):
            m = re.match(r"^(E\d{3})_", p.name)
            if not m:
                continue
            out[m.group(1)] = p
    return out


def known_eids(triage_dir: Path) -> set[str]:
    index_text = read_text_if_exists(triage_dir / "evidence" / "index.md")
    return set(re.findall(r"\bE\d{3}\b", index_text))


def assert_eids_exist(triage_dir: Path, eids: List[str]) -> None:
    known = known_eids(triage_dir)
    disk = set(evidence_files_on_disk(triage_dir).keys())
    missing = [e for e in eids if e not in known]
    missing_files = [e for e in eids if e not in disk]
    if missing:
        raise typer.BadParameter(f"Unknown EIDs (not in evidence/index.md): {', '.join(missing)}")
    if missing_files:
        raise typer.BadParameter(f"EIDs missing evidence files on disk: {', '.join(missing_files)}")

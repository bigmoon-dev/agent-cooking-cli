from __future__ import annotations

import re
from pathlib import Path
from typing import List

import typer

from .document_blocks import append_block, next_id
from .validate_rules import assert_eids_exist


def add_fact(*, tdir: Path, text: str, evidence: List[str]) -> str:
    eids = [e.strip().upper() for e in evidence if e.strip()]
    if not eids:
        raise typer.BadParameter("At least one --evidence E### is required")
    for e in eids:
        if not re.fullmatch(r"E\d{3}", e):
            raise typer.BadParameter(f"Invalid evidence id: {e}")
    assert_eids_exist(tdir, eids)

    facts_path = tdir / "facts.md"
    fid = next_id(facts_path, "F")
    line = f"{fid}: {text.strip()} ({', '.join(sorted(set(eids)))})"
    append_block(facts_path, line)
    return fid


def list_facts(*, tdir: Path) -> List[str]:
    facts_path = tdir / "facts.md"
    out: List[str] = []
    text = facts_path.read_text(encoding="utf-8") if facts_path.exists() else ""
    for line in text.splitlines():
        m = re.match(r"^(F\d{3}):\s*(.*)$", line)
        if not m:
            continue
        out.append(f"{m.group(1)}: {m.group(2)}")
    return out


def set_fact(*, tdir: Path, fid: str, text: str, evidence: List[str]) -> None:
    fid_n = fid.strip().upper()
    if not re.fullmatch(r"F\d{3}", fid_n):
        raise typer.BadParameter("--id must be like F001")

    eids = [e.strip().upper() for e in evidence if e.strip()]
    if not eids:
        raise typer.BadParameter("At least one --evidence E### is required")
    for e in eids:
        if not re.fullmatch(r"E\d{3}", e):
            raise typer.BadParameter(f"Invalid evidence id: {e}")
    assert_eids_exist(tdir, eids)

    facts_path = tdir / "facts.md"
    lines = facts_path.read_text(encoding="utf-8").splitlines() if facts_path.exists() else []
    updated = False
    out: List[str] = []
    replacement = f"{fid_n}: {text.strip()} ({', '.join(sorted(set(eids)))})"
    for line in lines:
        if re.match(rf"^{re.escape(fid_n)}:\s*", line):
            out.append(replacement)
            updated = True
        else:
            out.append(line)
    if not updated:
        raise typer.BadParameter(f"Fact id not found: {fid_n}")
    facts_path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")

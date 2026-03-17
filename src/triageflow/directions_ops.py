from __future__ import annotations

import re
from pathlib import Path
from typing import List

import typer

from .document_blocks import append_block, join_blocks, split_blocks
from .validate_rules import assert_eids_exist


def add_direction(
    *,
    tdir: Path,
    direction: str,
    evidence: List[str],
    next_test: str,
    falsify_if: str,
    confidence: str,
) -> str:
    eids = [e.strip().upper() for e in evidence if e.strip()]
    if not eids:
        raise typer.BadParameter("At least one --evidence E### is required")
    for e in eids:
        if not re.fullmatch(r"E\d{3}", e):
            raise typer.BadParameter(f"Invalid evidence id: {e}")
    assert_eids_exist(tdir, eids)

    directions_path = tdir / "directions.md"
    text = directions_path.read_text(encoding="utf-8") if directions_path.exists() else ""
    nums: list[int] = []
    for m in re.finditer(r"\bDIR-(\d+)\b", text):
        nums.append(int(m.group(1)))
    n = (max(nums) + 1) if nums else 1
    did = f"DIR-{n}"

    block = (
        f"{did} (Confidence: {confidence.strip()})\n"
        f"Direction: {direction.strip()}\n"
        f"Evidence chain: ({', '.join(sorted(set(eids)))})\n"
        + (f"Next minimal test: {next_test.strip()}\n" if next_test.strip() else "Next minimal test: \n")
        + (f"Falsify if: {falsify_if.strip()}\n" if falsify_if.strip() else "Falsify if: \n")
    )
    append_block(directions_path, block)
    return did


def list_directions(*, tdir: Path) -> List[str]:
    directions_path = tdir / "directions.md"
    text = directions_path.read_text(encoding="utf-8") if directions_path.exists() else ""
    blocks = split_blocks(text, r"^DIR-\d+\b.*")
    out: List[str] = []
    for b in blocks:
        if not b:
            continue
        header = b[0]
        mid = re.match(r"^(DIR-\d+)\b", header)
        if not mid:
            continue
        did = mid.group(1)
        conf_m = re.search(r"Confidence:\s*([^|)]+)", header)
        conf = conf_m.group(1).strip() if conf_m else "?"
        eids = sorted(set(re.findall(r"\bE\d{3}\b", "\n".join(b))))
        out.append(f"{did} [{conf}] EIDs: {', '.join(eids) if eids else 'none'}")
    return out


def prune_directions(*, tdir: Path, top_n: int) -> None:
    directions_path = tdir / "directions.md"
    text = directions_path.read_text(encoding="utf-8") if directions_path.exists() else ""
    blocks = split_blocks(text, r"^DIR-\d+\b.*")
    if not blocks:
        raise typer.BadParameter("No direction blocks found")
    kept = blocks[:top_n]
    directions_path.write_text(join_blocks(kept), encoding="utf-8")

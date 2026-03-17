from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

import typer

from .core import read_text_if_exists, write_text
from .validate_rules import evidence_files_on_disk, known_eids


def parse_evidence_index(tdir: Path) -> dict[str, dict[str, str]]:
    """Return mapping of EID -> {type, source, note} from evidence/index.md."""

    index_path = tdir / "evidence" / "index.md"
    text = read_text_if_exists(index_path)
    info: dict[str, dict[str, str]] = {}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) < 5:
            continue
        eid = cols[0]
        if not re.fullmatch(r"E\d{3}", eid):
            continue
        info[eid] = {"type": cols[1], "source": cols[2], "note": cols[4]}
    return info


def build_directions(*, tdir: Path, top_n: int, overwrite: bool) -> None:
    """Build Top directions from evidence-backed hypotheses (MVP scoring)."""

    directions_path = tdir / "directions.md"
    existing = read_text_if_exists(directions_path).strip()
    if existing and not overwrite:
        raise typer.BadParameter(f"{directions_path} exists. Re-run with --overwrite")

    ev_index = parse_evidence_index(tdir)
    known = known_eids(tdir)
    disk = set(evidence_files_on_disk(tdir).keys())

    hyp_text = read_text_if_exists(tdir / "hypotheses.md")
    if not re.search(r"^H\d{3}\b", hyp_text, flags=re.MULTILINE):
        raise typer.BadParameter("No hypotheses found. Add evidence-backed hypotheses first.")

    lines = hyp_text.splitlines()
    blocks: list[dict[str, object]] = []
    cur_id: Optional[str] = None
    cur_lines: List[str] = []
    for line in lines:
        m = re.match(r"^(H\d{3})\b(.*)$", line)
        if m:
            if cur_id is not None:
                blocks.append({"id": cur_id, "text": "\n".join(cur_lines)})
            cur_id = m.group(1)
            cur_lines = [line]
        else:
            if cur_id is not None:
                cur_lines.append(line)
    if cur_id is not None:
        blocks.append({"id": cur_id, "text": "\n".join(cur_lines)})

    scored: list[tuple[int, dict[str, object]]] = []
    for b in blocks:
        text = str(b["text"])
        eids: List[str] = sorted(set(re.findall(r"\bE\d{3}\b", text)))
        if not eids:
            continue
        if not any((e in known and e in disk) for e in eids):
            continue
        log_eids = [e for e in eids if ev_index.get(e, {}).get("type") == "log"]
        status_open = bool(re.search(r"Status:\s*Open\b", text, flags=re.IGNORECASE))
        score = 0
        score += len(eids)
        score += 2 * len(log_eids)
        if status_open:
            score += 2
        scored.append((score, {"id": b["id"], "eids": eids, "text": text, "score": score}))

    scored.sort(key=lambda t: (-t[0], str(t[1].get("id") or "")))
    top = [b for _, b in scored[:top_n]]

    if not top:
        raise typer.BadParameter(
            "No evidence-backed hypotheses found. Add evidence first, then cite real EIDs in hypotheses.md."
        )

    out_lines: List[str] = []
    out_lines.append("# Directions")
    out_lines.append("")
    out_lines.append("Generated from evidence-backed hypotheses.")
    out_lines.append("Rules: keep top 1-3 directions; each must cite EIDs.")
    out_lines.append("")

    for i, b in enumerate(top, start=1):
        eids = list(b["eids"])  # type: ignore[assignment]
        hid = str(b["id"])
        out_lines.append(f"DIR-{i} (From: {hid} | Confidence: Medium)")
        out_lines.append("Direction: <fill: component / chain / data / dependency / config>")
        out_lines.append(
            "Evidence chain: (" + ", ".join(eids[:5]) + (", ..." if len(eids) > 5 else "") + ")"
        )
        out_lines.append("Next minimal test: <one discriminative test to separate top directions>")
        out_lines.append("Falsify if: <what observation would kill this direction>")
        out_lines.append("")

    write_text(directions_path, "\n".join(out_lines).rstrip() + "\n")
    typer.echo(f"Wrote {directions_path} ({len(top)} directions)")

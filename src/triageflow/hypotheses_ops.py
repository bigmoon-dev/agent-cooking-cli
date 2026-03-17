from __future__ import annotations

import re
from pathlib import Path
from typing import List

import typer

from .document_blocks import append_block, join_blocks, next_id, split_blocks
from .validate_rules import assert_eids_exist


def add_hypothesis(
    *,
    tdir: Path,
    hypothesis: str,
    evidence: List[str],
    test: str,
    confidence: str,
    status: str,
) -> str:
    eids = [e.strip().upper() for e in evidence if e.strip()]
    if not eids:
        raise typer.BadParameter("At least one --evidence E### is required")
    for e in eids:
        if not re.fullmatch(r"E\d{3}", e):
            raise typer.BadParameter(f"Invalid evidence id: {e}")
    assert_eids_exist(tdir, eids)

    hyp_path = tdir / "hypotheses.md"
    hid = next_id(hyp_path, "H")
    block = (
        f"{hid} (Status: {status.strip()} | Confidence: {confidence.strip()})\n"
        f"Hypothesis: {hypothesis.strip()}\n"
        f"Evidence: ({', '.join(sorted(set(eids)))})\n"
        + (f"Test: {test.strip()}\n" if test.strip() else "Test: \n")
    )
    append_block(hyp_path, block)
    return hid


def list_hypotheses(*, tdir: Path) -> List[str]:
    hyp_path = tdir / "hypotheses.md"
    text = hyp_path.read_text(encoding="utf-8") if hyp_path.exists() else ""
    blocks = split_blocks(text, r"^H\d{3}\b.*")
    out: List[str] = []
    for b in blocks:
        if not b:
            continue
        header = b[0]
        hid_m = re.match(r"^(H\d{3})\b", header)
        if not hid_m:
            continue
        hid = hid_m.group(1)
        status_m = re.search(r"Status:\s*([^|)]+)", header)
        conf_m = re.search(r"Confidence:\s*([^|)]+)", header)
        status = status_m.group(1).strip() if status_m else "?"
        conf = conf_m.group(1).strip() if conf_m else "?"
        eids = sorted(set(re.findall(r"\bE\d{3}\b", "\n".join(b))))
        out.append(f"{hid} [{status}/{conf}] EIDs: {', '.join(eids) if eids else 'none'}")
    return out


def close_hypothesis(*, tdir: Path, hid: str, reason: str) -> None:
    hyp_path = tdir / "hypotheses.md"
    text = hyp_path.read_text(encoding="utf-8") if hyp_path.exists() else ""
    blocks = split_blocks(text, r"^H\d{3}\b.*")
    hid_n = hid.strip().upper()
    if not re.fullmatch(r"H\d{3}", hid_n):
        raise typer.BadParameter("--id must be like H001")

    found = False
    out_blocks: List[List[str]] = []
    for b in blocks:
        if not b:
            continue
        header = b[0]
        if header.startswith(hid_n + " ") or header == hid_n or header.startswith(hid_n + "("):
            new_header = re.sub(r"Status:\s*[^|)]+", "Status: Closed", header)
            if new_header == header and "Status:" not in header:
                new_header = header + " | Status: Closed"
            b2 = [new_header] + b[1:]
            if reason.strip():
                b2.append(f"Closed because: {reason.strip()}")
            out_blocks.append(b2)
            found = True
        else:
            out_blocks.append(b)

    if not found:
        raise typer.BadParameter(f"Hypothesis id not found: {hid_n}")
    hyp_path.write_text(join_blocks(out_blocks), encoding="utf-8")

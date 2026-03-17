from __future__ import annotations

import re
from pathlib import Path

import typer

from .core import load_yaml, read_text_if_exists
from .evidence import latest_eid
from .profile import get_round_fields, load_active_profile, profile_required_evidence
from .validate_rules import evidence_files_on_disk, known_eids


def _split_blocks(text: str, header_re: str) -> list[list[str]]:
    lines = text.splitlines()
    hpat = re.compile(header_re)
    blocks: list[list[str]] = []
    cur: list[str] = []
    for line in lines:
        if hpat.match(line):
            if cur:
                blocks.append(cur)
            cur = [line]
        else:
            if cur:
                cur.append(line)
    if cur:
        blocks.append(cur)
    return blocks


def _has_real_hypothesis(tdir: Path) -> bool:
    known = known_eids(tdir)
    disk = set(evidence_files_on_disk(tdir).keys())
    hyp_text = read_text_if_exists(tdir / "hypotheses.md")
    blocks = _split_blocks(hyp_text, r"^H\d{3}\b.*")
    for b in blocks:
        body = "\n".join(b)
        eids = set(re.findall(r"\bE\d{3}\b", body))
        if not any((e in known and e in disk) for e in eids):
            continue
        # Template has empty "Hypothesis:". Require substantive content.
        if re.search(r"^Hypothesis:\s*\S", body, flags=re.MULTILINE):
            return True
    return False


def _has_generated_directions(tdir: Path) -> bool:
    known = known_eids(tdir)
    disk = set(evidence_files_on_disk(tdir).keys())
    dtext = read_text_if_exists(tdir / "directions.md")
    blocks = _split_blocks(dtext, r"^DIR-\d+\b.*")
    for b in blocks:
        header = b[0] if b else ""
        body = "\n".join(b)
        eids = set(re.findall(r"\bE\d{3}\b", body))
        if not any((e in known and e in disk) for e in eids):
            continue
        # Template directions don't have "From: H###" in header.
        if re.search(r"\bFrom:\s*H\d{3}\b", header):
            return True
    return False


def _is_missing_case_field(case: dict, key: str) -> bool:
    if key not in case:
        return True
    v = case.get(key)
    if v is None:
        return True
    if isinstance(v, str):
        return not v.strip()
    if isinstance(v, list):
        return len(v) == 0
    return False


def print_next(tdir: Path) -> None:
    """Print the recommended golden-path next command based on workspace state."""

    prof_path = tdir / "profile.yaml"
    case_path = tdir / "case.yaml"
    if not prof_path.exists():
        typer.echo("Next: init --profile <profile_id>")
        raise typer.Exit(code=0)
    if not case_path.exists():
        typer.echo("Next: round run 0")
        raise typer.Exit(code=0)

    case = load_yaml(case_path)
    profile = load_active_profile(triage_dir=tdir, load_yaml_func=load_yaml)

    required0 = get_round_fields(profile, 0)
    if required0 and any(_is_missing_case_field(case, k) for k in required0):
        typer.echo("Next: round run 0")
        raise typer.Exit(code=0)

    required1 = get_round_fields(profile, 1)
    if required1 and any(_is_missing_case_field(case, k) for k in required1):
        typer.echo("Next: round run 1")
        raise typer.Exit(code=0)

    index_path = tdir / "evidence" / "index.md"
    if not index_path.exists() or not re.search(r"\bE\d{3}\b", read_text_if_exists(index_path)):
        required_ev = profile_required_evidence(profile)
        if "uart_log" in required_ev:
            uart_attached = isinstance(case.get("uart_log_path"), str) and str(case.get("uart_log_path")).strip()
            anchors = case.get("anchor_keywords")
            anchors_ok = isinstance(anchors, list) and any(str(a).strip() for a in anchors)
            if uart_attached and anchors_ok:
                typer.echo("Next: evidence hunt")
            else:
                hint = "panic"
                if isinstance(anchors, list) and anchors:
                    for a in anchors:
                        s = str(a).strip()
                        if s:
                            hint = s
                            break
                typer.echo(f"Next: evidence add-log --log-path <uart.log> --pattern {hint}")
        else:
            typer.echo("Next: evidence add-text --source <source> --note <fact> --content <text>")
        raise typer.Exit(code=0)

    facts_text = read_text_if_exists(tdir / "facts.md")
    facts_exist = bool(re.search(r"^F\d{3}:\s*.+\bE\d{3}\b", facts_text, flags=re.MULTILINE))
    if not facts_exist:
        eid = latest_eid(tdir) or "E001"
        typer.echo(f"Next: facts add --text <fact> --evidence {eid}")
        raise typer.Exit(code=0)

    if not _has_real_hypothesis(tdir):
        eid = latest_eid(tdir) or "E001"
        typer.echo(f"Next: hypotheses add --hypothesis <...> --evidence {eid}")
        raise typer.Exit(code=0)

    if not _has_generated_directions(tdir):
        typer.echo("Next: direction-build --overwrite")
        raise typer.Exit(code=0)

    typer.echo("Next: validate")

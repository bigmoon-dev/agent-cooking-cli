from __future__ import annotations

import re
from collections import deque
from pathlib import Path
from typing import List, Optional, Tuple

import typer

from .core import atomic_write_text, load_yaml, now_iso, read_text_if_exists
from .workspace_lock import workspace_lock


def parse_existing_eids(index_md: str) -> List[int]:
    nums: List[int] = []
    for m in re.finditer(r"\bE(\d{3})\b", index_md):
        nums.append(int(m.group(1)))
    return nums


def next_eid(triage_dir: Path) -> str:
    index_path = triage_dir / "evidence" / "index.md"
    existing = parse_existing_eids(read_text_if_exists(index_path))
    n = (max(existing) + 1) if existing else 1
    return f"E{n:03d}"


def latest_eid(triage_dir: Path) -> Optional[str]:
    index_text = read_text_if_exists(triage_dir / "evidence" / "index.md")
    eids = re.findall(r"\bE\d{3}\b", index_text)
    if not eids:
        return None
    return list(dict.fromkeys(eids))[-1]


def append_evidence_index(triage_dir: Path, *, eid: str, etype: str, source: str, note: str) -> None:
    index_path = triage_dir / "evidence" / "index.md"
    text = read_text_if_exists(index_path)
    if not text.strip():
        text = (
            "| Evidence ID | Type | Source | Time | What it shows (fact only) |\n"
            "|---|---|---|---|---|\n"
        )
    line = f"| {eid} | {etype} | {source} | {now_iso()} | {note} |\n"
    atomic_write_text(index_path, text + line)


def _evidence_lock_path(tdir: Path) -> Path:
    return tdir / "evidence" / ".lock"


def _create_evidence_record(
    *,
    tdir: Path,
    etype_norm: str,
    source: str,
    note: str,
    body_text: str,
    out_path: Path,
) -> Tuple[str, Path]:
    """Allocate EID, write evidence file, then update index under one lock.

    Failure compensation:
    - If evidence write fails: do not touch index.
    - If index update fails after evidence write: attempt to delete the evidence file.
    """

    lock_path = _evidence_lock_path(tdir)
    with workspace_lock(lock_path):
        eid = next_eid(tdir)
        if out_path.name.startswith("E"):
            # Caller may have already formatted filename; ensure it matches allocated eid.
            out_path = out_path.with_name(re.sub(r"^E\d{3}", eid, out_path.name))

        header = (
            f"EID: {eid}\n"
            f"Type: {etype_norm}\n"
            f"Source: {source}\n"
            f"Captured: {now_iso()}\n"
            f"Note: {note}\n"
            "---\n"
        )
        try:
            atomic_write_text(out_path, header + body_text.rstrip() + "\n")
        except Exception:
            raise

        try:
            append_evidence_index(tdir, eid=eid, etype=etype_norm, source=source, note=note)
        except Exception:
            try:
                out_path.unlink()
            except OSError:
                pass
            raise

        return eid, out_path


def resolve_uart_log_path(tdir: Path) -> Optional[Path]:
    case = load_yaml(tdir / "case.yaml")
    p = case.get("uart_log_path")
    if isinstance(p, str) and p.strip():
        return Path(p)
    return None


def capture_log_windows(
    *,
    tdir: Path,
    log_path: Path,
    pattern: List[str],
    before: int,
    after: int,
    max_matches: int,
    note: str,
) -> List[str]:
    combined = "|".join([f"(?:{p})" for p in pattern if p.strip()])
    if not combined:
        raise typer.BadParameter("At least one --pattern is required")
    try:
        rx = re.compile(combined)
    except re.error as e:
        raise typer.BadParameter(f"Invalid regex pattern: {e}")

    buf_before: deque[tuple[int, str]] = deque(maxlen=before)
    captures = 0
    line_no = 0
    created: List[str] = []

    def _write_capture(match_line_no: int, before_lines: List[tuple[int, str]], match_line: str, after_lines: List[tuple[int, str]]) -> None:
        nonlocal captures
        start = before_lines[0][0] if before_lines else match_line_no
        end = after_lines[-1][0] if after_lines else match_line_no
        source = f"{log_path}:{start}-{end}"
        out_path = tdir / "evidence" / "log" / "E000_log.txt"
        body: List[str] = []
        for ln, s in before_lines:
            body.append(f"{ln}: {s}")
        body.append(f"{match_line_no}: {match_line}")
        for ln, s in after_lines:
            body.append(f"{ln}: {s}")
        eid, real_path = _create_evidence_record(
            tdir=tdir,
            etype_norm="log",
            source=source,
            note=note,
            body_text=(
                "Match: /" + combined + f"/ at line {match_line_no}\n" + "\n".join(body)
            ),
            out_path=out_path,
        )
        created.append(eid)
        captures += 1

    with log_path.open("r", encoding="utf-8", errors="replace") as f:
        it = iter(f)
        for raw in it:
            line_no += 1
            line = raw.rstrip("\n")
            if rx.search(line):
                before_lines = list(buf_before)
                after_lines: List[tuple[int, str]] = []
                for _ in range(after):
                    try:
                        nxt = next(it)
                    except StopIteration:
                        break
                    line_no += 1
                    after_lines.append((line_no, nxt.rstrip("\n")))
                _write_capture(line_no - len(after_lines), before_lines, line, after_lines)
                buf_before.clear()
                for item in after_lines[-before:]:
                    buf_before.append(item)
                if captures >= max_matches:
                    break
            else:
                buf_before.append((line_no, line))

    return created


def _evidence_folder_for_type(etype_norm: str) -> str:
    # Historical layout:
    # - add-text uses type=text but stores under evidence/cmd
    # - add-log stores under evidence/log
    return "cmd" if etype_norm == "text" else etype_norm


def add_evidence_snippet(
    *,
    tdir: Path,
    etype: str,
    source: str,
    note: str,
    snippet: str,
) -> Tuple[str, Path]:
    etype_norm = etype.strip().lower()
    if etype_norm not in {"log", "code", "cmd", "text"}:
        raise typer.BadParameter("--type must be one of: log, code, cmd, text")

    folder = tdir / "evidence" / _evidence_folder_for_type(etype_norm)
    out_path = folder / f"E000_{etype_norm}.txt"
    return _create_evidence_record(
        tdir=tdir,
        etype_norm=etype_norm,
        source=source,
        note=note,
        body_text=snippet,
        out_path=out_path,
    )


def capture_log_range(
    *,
    tdir: Path,
    log_path: Path,
    line_start: int,
    line_end: int,
    note: str,
) -> Tuple[str, Path]:
    if line_start < 1 or line_end < 1:
        raise typer.BadParameter("Line numbers must be >= 1")
    if line_end < line_start:
        raise typer.BadParameter("--line-end must be >= --line-start")

    out_lines: List[str] = []
    with log_path.open("r", encoding="utf-8", errors="replace") as f:
        for i, raw in enumerate(f, start=1):
            if i < line_start:
                continue
            if i > line_end:
                break
            out_lines.append(f"{i}: {raw.rstrip()}")

    if not out_lines:
        raise typer.BadParameter("Selected line range is empty")

    source = f"{log_path}:{line_start}-{line_end}"
    out_path = tdir / "evidence" / "log" / "E000_log.txt"
    return _create_evidence_record(
        tdir=tdir,
        etype_norm="log",
        source=source,
        note=note,
        body_text="\n".join(out_lines),
        out_path=out_path,
    )

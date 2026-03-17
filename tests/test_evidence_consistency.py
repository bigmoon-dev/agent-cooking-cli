from __future__ import annotations

from pathlib import Path

import pytest

import triageflow.evidence as evidence


def _triage_dir(tmp_path: Path) -> Path:
    tdir = tmp_path / "triage"
    (tdir / "evidence" / "log").mkdir(parents=True, exist_ok=True)
    (tdir / "evidence" / "cmd").mkdir(parents=True, exist_ok=True)
    (tdir / "evidence" / "code").mkdir(parents=True, exist_ok=True)
    return tdir


def test_add_evidence_snippet_writes_file_and_index(tmp_path: Path) -> None:
    tdir = _triage_dir(tmp_path)
    eid, out_path = evidence.add_evidence_snippet(
        tdir=tdir,
        etype="text",
        source="unit-test",
        note="test note",
        snippet="some content",
    )
    assert out_path.exists()
    assert eid in out_path.name
    idx = (tdir / "evidence" / "index.md").read_text(encoding="utf-8")
    assert eid in idx


def test_capture_log_range_writes_file_and_index(tmp_path: Path) -> None:
    tdir = _triage_dir(tmp_path)
    log = tmp_path / "uart.log"
    log.write_text("a\nb\nc\n", encoding="utf-8")
    eid, out_path = evidence.capture_log_range(
        tdir=tdir,
        log_path=log,
        line_start=1,
        line_end=2,
        note="range",
    )
    assert out_path.exists()
    idx = (tdir / "evidence" / "index.md").read_text(encoding="utf-8")
    assert eid in idx


def test_capture_log_windows_writes_all_files_and_index(tmp_path: Path) -> None:
    tdir = _triage_dir(tmp_path)
    log = tmp_path / "uart.log"
    log.write_text("boot\npanic: watchdog\nreboot\n", encoding="utf-8")
    eids = evidence.capture_log_windows(
        tdir=tdir,
        log_path=log,
        pattern=["panic"],
        before=1,
        after=1,
        max_matches=2,
        note="anchor",
    )
    assert eids
    idx = (tdir / "evidence" / "index.md").read_text(encoding="utf-8")
    for eid in eids:
        assert eid in idx
        assert (tdir / "evidence" / "log" / f"{eid}_log.txt").exists()


def test_index_failure_compensates_by_deleting_evidence_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tdir = _triage_dir(tmp_path)

    def boom(*args, **kwargs):
        raise RuntimeError("index write failed")

    monkeypatch.setattr(evidence, "append_evidence_index", boom)
    with pytest.raises(RuntimeError):
        evidence.add_evidence_snippet(
            tdir=tdir,
            etype="text",
            source="unit-test",
            note="test note",
            snippet="content",
        )

    # Evidence file should have been removed (best-effort compensation).
    any_files = list((tdir / "evidence" / "cmd").glob("E[0-9][0-9][0-9]_*.txt"))
    assert any_files == []

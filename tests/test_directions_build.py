"""Tests for directions.py — scoring and direction-building algorithm."""

from __future__ import annotations

from pathlib import Path

import pytest

from triageflow.directions import build_directions


# -- Helpers -----------------------------------------------------------------


def _make_tdir(tmp_path: Path) -> Path:
    tdir = tmp_path / "triage"
    tdir.mkdir()
    (tdir / "evidence" / "log").mkdir(parents=True)
    (tdir / "evidence" / "code").mkdir(parents=True)
    (tdir / "evidence" / "cmd").mkdir(parents=True)
    return tdir


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _add_evidence(tdir: Path, eid: str, etype: str = "cmd") -> None:
    """Register an EID in the index and write its on-disk file."""
    index_path = tdir / "evidence" / "index.md"
    prev = index_path.read_text(encoding="utf-8") if index_path.exists() else (
        "| Evidence ID | Type | Source | Time | What it shows (fact only) |\n"
        "|---|---|---|---|---|\n"
    )
    prev += f"| {eid} | {etype} | src | t | note |\n"
    index_path.write_text(prev, encoding="utf-8")
    folder = "log" if etype == "log" else "cmd"
    (tdir / "evidence" / folder / f"{eid}_{etype}.txt").write_text("data", encoding="utf-8")


# -- Tests -------------------------------------------------------------------


def test_build_no_hypotheses(tmp_path: Path) -> None:
    """No hypotheses at all → BadParameter."""
    tdir = _make_tdir(tmp_path)
    _add_evidence(tdir, "E001")
    _write_text(tdir / "hypotheses.md", "# Hypotheses\n\nNothing here.\n")
    with pytest.raises(Exception, match="No hypotheses"):
        build_directions(tdir=tdir, top_n=3, overwrite=True)


def test_build_hypotheses_no_real_evidence(tmp_path: Path) -> None:
    """Hypothesis cites EIDs that don't exist on disk → no directions (BadParameter)."""
    tdir = _make_tdir(tmp_path)
    # Write index with E001 but do NOT create the evidence file on disk
    _write_text(
        tdir / "evidence" / "index.md",
        "| Evidence ID | Type | Source | Time | What it shows (fact only) |\n"
        "|---|---|---|---|---|\n"
        "| E001 | cmd | src | t | note |\n",
    )
    _write_text(tdir / "hypotheses.md", (
        "# Hypotheses\n\n"
        "H001 (Status: Open | Confidence: Medium)\n"
        "Hypothesis: Something\n"
        "Evidence: (E001)\n"
    ))
    with pytest.raises(Exception, match="No evidence-backed"):
        build_directions(tdir=tdir, top_n=3, overwrite=True)


def test_build_one_backed_hypothesis(tmp_path: Path) -> None:
    """Single evidence-backed hypothesis → produces exactly 1 direction."""
    tdir = _make_tdir(tmp_path)
    _add_evidence(tdir, "E001")
    _write_text(tdir / "hypotheses.md", (
        "# Hypotheses\n\n"
        "H001 (Status: Open | Confidence: Medium)\n"
        "Hypothesis: Root cause A\n"
        "Evidence: (E001)\n"
        "Test: verify A\n"
    ))
    build_directions(tdir=tdir, top_n=3, overwrite=True)
    text = (tdir / "directions.md").read_text(encoding="utf-8")
    assert "DIR-1" in text
    assert "H001" in text
    assert "DIR-2" not in text


def test_build_ranks_by_score(tmp_path: Path) -> None:
    """Hypothesis with more EIDs ranks higher."""
    tdir = _make_tdir(tmp_path)
    _add_evidence(tdir, "E001")
    _add_evidence(tdir, "E002")
    _add_evidence(tdir, "E003")
    _write_text(tdir / "hypotheses.md", (
        "# Hypotheses\n\n"
        "H001 (Status: Open | Confidence: Medium)\n"
        "Hypothesis: Only one evidence\n"
        "Evidence: (E001)\n"
        "Test: t\n\n"
        "H002 (Status: Open | Confidence: Medium)\n"
        "Hypothesis: Multiple evidences\n"
        "Evidence: (E001, E002, E003)\n"
        "Test: t\n"
    ))
    build_directions(tdir=tdir, top_n=3, overwrite=True)
    text = (tdir / "directions.md").read_text(encoding="utf-8")
    # DIR-1 should come from H002 (higher score), DIR-2 from H001
    dir1_pos = text.index("DIR-1")
    dir2_pos = text.index("DIR-2")
    assert dir1_pos < dir2_pos
    # H002 should appear first (in DIR-1)
    assert "DIR-1 (From: H002" in text


def test_log_eids_score_higher(tmp_path: Path) -> None:
    """Hypothesis backed by log-type evidence scores higher than cmd-type."""
    tdir = _make_tdir(tmp_path)
    _add_evidence(tdir, "E001", etype="cmd")
    _add_evidence(tdir, "E002", etype="log")
    _write_text(tdir / "hypotheses.md", (
        "# Hypotheses\n\n"
        "H001 (Status: Open | Confidence: Medium)\n"
        "Hypothesis: cmd only\n"
        "Evidence: (E001)\n"
        "Test: t\n\n"
        "H002 (Status: Open | Confidence: Medium)\n"
        "Hypothesis: log evidence\n"
        "Evidence: (E002)\n"
        "Test: t\n"
    ))
    build_directions(tdir=tdir, top_n=3, overwrite=True)
    text = (tdir / "directions.md").read_text(encoding="utf-8")
    # H002 (log) should rank first → DIR-1
    assert "DIR-1 (From: H002" in text


def test_top_n_limits(tmp_path: Path) -> None:
    """top_n=1 produces only 1 direction even with multiple hypotheses."""
    tdir = _make_tdir(tmp_path)
    _add_evidence(tdir, "E001")
    _add_evidence(tdir, "E002")
    _write_text(tdir / "hypotheses.md", (
        "# Hypotheses\n\n"
        "H001 (Status: Open | Confidence: Medium)\n"
        "Hypothesis: A\n"
        "Evidence: (E001)\n"
        "Test: t\n\n"
        "H002 (Status: Open | Confidence: Medium)\n"
        "Hypothesis: B\n"
        "Evidence: (E002)\n"
        "Test: t\n"
    ))
    build_directions(tdir=tdir, top_n=1, overwrite=True)
    text = (tdir / "directions.md").read_text(encoding="utf-8")
    assert "DIR-1" in text
    assert "DIR-2" not in text


def test_overwrite_false_existing_raises(tmp_path: Path) -> None:
    """overwrite=False when directions.md exists → BadParameter."""
    tdir = _make_tdir(tmp_path)
    _add_evidence(tdir, "E001")
    _write_text(tdir / "directions.md", "# Directions\n\nDIR-1 old\n")
    _write_text(tdir / "hypotheses.md", (
        "# Hypotheses\n\n"
        "H001 (Status: Open)\n"
        "Hypothesis: X\n"
        "Evidence: (E001)\n"
    ))
    with pytest.raises(Exception, match="exists.*overwrite"):
        build_directions(tdir=tdir, top_n=3, overwrite=False)


def test_overwrite_true_replaces(tmp_path: Path) -> None:
    """overwrite=True replaces existing directions."""
    tdir = _make_tdir(tmp_path)
    _add_evidence(tdir, "E001")
    _write_text(tdir / "directions.md", "# Directions\n\nold content\n")
    _write_text(tdir / "hypotheses.md", (
        "# Hypotheses\n\n"
        "H001 (Status: Open | Confidence: Medium)\n"
        "Hypothesis: New thing\n"
        "Evidence: (E001)\n"
        "Test: t\n"
    ))
    build_directions(tdir=tdir, top_n=3, overwrite=True)
    text = (tdir / "directions.md").read_text(encoding="utf-8")
    assert "old content" not in text
    assert "DIR-1" in text
    assert "H001" in text

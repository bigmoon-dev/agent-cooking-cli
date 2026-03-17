from __future__ import annotations

from pathlib import Path

import pytest

from triageflow.directions_ops import add_direction, prune_directions
from triageflow.facts_ops import add_fact, set_fact
from triageflow.hypotheses_ops import add_hypothesis, close_hypothesis


def _setup_triage(tmp_path: Path) -> Path:
    tdir = tmp_path / "triage"
    (tdir / "evidence" / "cmd").mkdir(parents=True, exist_ok=True)
    (tdir / "evidence" / "log").mkdir(parents=True, exist_ok=True)
    (tdir / "evidence" / "code").mkdir(parents=True, exist_ok=True)
    # Minimal evidence index + dummy evidence file to satisfy assert_eids_exist
    (tdir / "evidence" / "cmd" / "E001_text.txt").write_text("x", encoding="utf-8")
    (tdir / "evidence" / "index.md").write_text(
        "| Evidence ID | Type | Source | Time | What it shows (fact only) |\n"
        "|---|---|---|---|---|\n"
        "| E001 | cmd | s | t | n |\n",
        encoding="utf-8",
    )
    return tdir


def test_facts_add_and_set(tmp_path: Path) -> None:
    tdir = _setup_triage(tmp_path)
    fid = add_fact(tdir=tdir, text="fact", evidence=["E001"])
    assert fid == "F001"
    set_fact(tdir=tdir, fid=fid, text="fact2", evidence=["E001"])
    txt = (tdir / "facts.md").read_text(encoding="utf-8")
    assert "fact2" in txt


def test_hypotheses_add_and_close(tmp_path: Path) -> None:
    tdir = _setup_triage(tmp_path)
    hid = add_hypothesis(
        tdir=tdir,
        hypothesis="h",
        evidence=["E001"],
        test="",
        confidence="Medium",
        status="Open",
    )
    assert hid == "H001"
    close_hypothesis(tdir=tdir, hid=hid, reason="because")
    txt = (tdir / "hypotheses.md").read_text(encoding="utf-8")
    assert "Status: Closed" in txt


def test_directions_add_and_prune(tmp_path: Path) -> None:
    tdir = _setup_triage(tmp_path)
    did1 = add_direction(
        tdir=tdir,
        direction="d1",
        evidence=["E001"],
        next_test="",
        falsify_if="",
        confidence="Medium",
    )
    did2 = add_direction(
        tdir=tdir,
        direction="d2",
        evidence=["E001"],
        next_test="",
        falsify_if="",
        confidence="Medium",
    )
    assert did1 == "DIR-1" and did2 == "DIR-2"
    prune_directions(tdir=tdir, top_n=1)
    txt = (tdir / "directions.md").read_text(encoding="utf-8")
    assert "DIR-1" in txt
    assert "DIR-2" not in txt


def test_ops_reject_unknown_eid(tmp_path: Path) -> None:
    tdir = _setup_triage(tmp_path)
    with pytest.raises(Exception):
        add_fact(tdir=tdir, text="fact", evidence=["E999"])

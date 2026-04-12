"""Tests for navigator.py — the golden-path state machine (print_next)."""

from __future__ import annotations

from pathlib import Path

import click
import pytest
import yaml

from triageflow.navigator import print_next


# -- Helpers -----------------------------------------------------------------

DESIGN_PROFILE = {
    "profile_id": "design_system_v1",
    "rounds": [
        {"id": 0, "fields": ["title", "problem_statement", "goals"]},
        {"id": 1, "fields": ["current_state", "options", "decision"]},
    ],
}

EMBEDDED_PROFILE = {
    "profile_id": "embedded_system_v1",
    "required_evidence": ["uart_log"],
    "rounds": [
        {"id": 0, "fields": ["symptom", "impact_scope"]},
        {"id": 1, "fields": ["uart_log_format", "anchor_keywords"]},
    ],
}


def _make_tdir(tmp_path: Path) -> Path:
    """Create the bare triage directory skeleton."""
    tdir = tmp_path / "triage"
    tdir.mkdir()
    (tdir / "evidence" / "log").mkdir(parents=True)
    (tdir / "evidence" / "code").mkdir(parents=True)
    (tdir / "evidence" / "cmd").mkdir(parents=True)
    return tdir


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _add_evidence(tdir: Path, eid: str = "E001", etype: str = "cmd") -> None:
    """Write a minimal evidence file and index entry so the EID is known+on-disk."""
    index_path = tdir / "evidence" / "index.md"
    prev = index_path.read_text(encoding="utf-8") if index_path.exists() else (
        "| Evidence ID | Type | Source | Time | What it shows (fact only) |\n"
        "|---|---|---|---|---|\n"
    )
    prev += f"| {eid} | {etype} | src | t | note |\n"
    index_path.write_text(prev, encoding="utf-8")
    folder = "log" if etype == "log" else "cmd"
    (tdir / "evidence" / folder / f"{eid}_{etype}.txt").write_text("data", encoding="utf-8")


def _capture(capsys, tdir: Path) -> str:
    """Call print_next and return its stdout.

    Most branches raise click.exceptions.Exit(code=0).
    The final "validate" branch just returns normally.
    """
    try:
        print_next(tdir)
    except click.exceptions.Exit as exc:
        assert exc.exit_code == 0
    return capsys.readouterr().out


# -- Tests -------------------------------------------------------------------


def test_no_profile(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """No profile.yaml → suggests init."""
    tdir = _make_tdir(tmp_path)
    out = _capture(capsys, tdir)
    assert "init" in out
    assert "--profile" in out


def test_no_case(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Profile exists but no case.yaml → suggests round run 0."""
    tdir = _make_tdir(tmp_path)
    _write_yaml(tdir / "profile.yaml", DESIGN_PROFILE)
    out = _capture(capsys, tdir)
    assert "round run 0" in out


def test_case_missing_round0(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """case.yaml exists but round-0 fields are empty → suggests round run 0."""
    tdir = _make_tdir(tmp_path)
    _write_yaml(tdir / "profile.yaml", DESIGN_PROFILE)
    _write_yaml(tdir / "case.yaml", {"title": "", "problem_statement": "", "goals": []})
    out = _capture(capsys, tdir)
    assert "round run 0" in out


def test_case_missing_round1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Round-0 complete but round-1 fields missing → suggests round run 1."""
    tdir = _make_tdir(tmp_path)
    _write_yaml(tdir / "profile.yaml", DESIGN_PROFILE)
    _write_yaml(tdir / "case.yaml", {
        "title": "Design X",
        "problem_statement": "We need X",
        "goals": ["goal1"],
        # round-1 fields missing
    })
    out = _capture(capsys, tdir)
    assert "round run 1" in out


def test_no_evidence_design_profile(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Design profile (no uart_log) with no evidence → suggests evidence add-text."""
    tdir = _make_tdir(tmp_path)
    _write_yaml(tdir / "profile.yaml", DESIGN_PROFILE)
    _write_yaml(tdir / "case.yaml", {
        "title": "Design X",
        "problem_statement": "We need X",
        "goals": ["goal1"],
        "current_state": "old",
        "options": "A or B",
        "decision": "A",
    })
    out = _capture(capsys, tdir)
    assert "evidence add-text" in out


def test_no_evidence_embedded_uart_no_log_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Embedded profile with uart_log requirement and no uart_log_path → suggests evidence add-log."""
    tdir = _make_tdir(tmp_path)
    _write_yaml(tdir / "profile.yaml", EMBEDDED_PROFILE)
    _write_yaml(tdir / "case.yaml", {
        "symptom": "crash",
        "impact_scope": "all",
        "uart_log_format": "text",
        "anchor_keywords": ["panic"],
    })
    out = _capture(capsys, tdir)
    assert "evidence add-log" in out


def test_no_evidence_embedded_uart_with_log_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Embedded profile with uart_log_path and anchor_keywords set → suggests evidence hunt."""
    tdir = _make_tdir(tmp_path)
    _write_yaml(tdir / "profile.yaml", EMBEDDED_PROFILE)
    _write_yaml(tdir / "case.yaml", {
        "symptom": "crash",
        "impact_scope": "all",
        "uart_log_format": "text",
        "anchor_keywords": ["panic"],
        "uart_log_path": "/tmp/uart.log",
    })
    out = _capture(capsys, tdir)
    assert "evidence hunt" in out


def test_no_facts(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Evidence exists but no facts → suggests facts add."""
    tdir = _make_tdir(tmp_path)
    _write_yaml(tdir / "profile.yaml", DESIGN_PROFILE)
    _write_yaml(tdir / "case.yaml", {
        "title": "X", "problem_statement": "Y", "goals": ["g"],
        "current_state": "old", "options": "A", "decision": "A",
    })
    _add_evidence(tdir, "E001")
    out = _capture(capsys, tdir)
    assert "facts add" in out


def test_no_hypotheses(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Facts exist but no real hypotheses → suggests hypotheses add."""
    tdir = _make_tdir(tmp_path)
    _write_yaml(tdir / "profile.yaml", DESIGN_PROFILE)
    _write_yaml(tdir / "case.yaml", {
        "title": "X", "problem_statement": "Y", "goals": ["g"],
        "current_state": "old", "options": "A", "decision": "A",
    })
    _add_evidence(tdir, "E001")
    _write_text(tdir / "facts.md", "# Facts\n\nF001: Some fact E001\n")
    out = _capture(capsys, tdir)
    assert "hypotheses add" in out


def test_no_generated_directions(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Hypotheses exist but no generated directions → suggests direction-build."""
    tdir = _make_tdir(tmp_path)
    _write_yaml(tdir / "profile.yaml", DESIGN_PROFILE)
    _write_yaml(tdir / "case.yaml", {
        "title": "X", "problem_statement": "Y", "goals": ["g"],
        "current_state": "old", "options": "A", "decision": "A",
    })
    _add_evidence(tdir, "E001")
    _write_text(tdir / "facts.md", "# Facts\n\nF001: Some fact E001\n")
    _write_text(tdir / "hypotheses.md", (
        "# Hypotheses\n\n"
        "H001 (Status: Open | Confidence: Medium)\n"
        "Hypothesis: Something is wrong\n"
        "Evidence: (E001)\n"
        "Test: check\n"
    ))
    out = _capture(capsys, tdir)
    assert "direction-build" in out


def test_all_complete(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Everything is in place → suggests validate."""
    tdir = _make_tdir(tmp_path)
    _write_yaml(tdir / "profile.yaml", DESIGN_PROFILE)
    _write_yaml(tdir / "case.yaml", {
        "title": "X", "problem_statement": "Y", "goals": ["g"],
        "current_state": "old", "options": "A", "decision": "A",
    })
    _add_evidence(tdir, "E001")
    _write_text(tdir / "facts.md", "# Facts\n\nF001: Some fact E001\n")
    _write_text(tdir / "hypotheses.md", (
        "# Hypotheses\n\n"
        "H001 (Status: Open | Confidence: Medium)\n"
        "Hypothesis: Something is wrong\n"
        "Evidence: (E001)\n"
        "Test: check\n"
    ))
    _write_text(tdir / "directions.md", (
        "# Directions\n\n"
        "DIR-1 (From: H001 | Confidence: Medium)\n"
        "Direction: arch\n"
        "Evidence chain: (E001)\n"
        "Next minimal test: t\n"
        "Falsify if: f\n"
    ))
    out = _capture(capsys, tdir)
    assert "validate" in out


def test_active_workflow_phase_validate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Active workflow phase (implement/review/deliver/validate) → suggests validate."""
    tdir = _make_tdir(tmp_path)
    _write_yaml(tdir / "profile.yaml", DESIGN_PROFILE)
    _write_yaml(tdir / "case.yaml", {
        "title": "X", "problem_statement": "Y", "goals": ["g"],
    })
    _write_yaml(tdir / "workflow_state.yaml", {"current_phase": "implement"})
    out = _capture(capsys, tdir)
    assert "validate" in out

from __future__ import annotations

from pathlib import Path

import pytest
import typer

import triageflow.core as core
from triageflow.evidence import add_evidence_snippet
from triageflow.facts_ops import add_fact
from triageflow.hypotheses_ops import add_hypothesis, close_hypothesis
from triageflow.validate import validate_workspace


def setup_function() -> None:
    core._event_hooks.clear()
    core._hook_error_handler = None


def _triage_dir(tmp_path: Path) -> Path:
    tdir = tmp_path / "triage"
    (tdir / "evidence" / "log").mkdir(parents=True, exist_ok=True)
    (tdir / "evidence" / "cmd").mkdir(parents=True, exist_ok=True)
    (tdir / "evidence" / "code").mkdir(parents=True, exist_ok=True)
    return tdir


def test_evidence_added_hook_receives_context(tmp_path: Path) -> None:
    tdir = _triage_dir(tmp_path)
    received = []

    core.register_hook("evidence.added", lambda **ctx: received.append(ctx))

    eid, out_path = add_evidence_snippet(
        tdir=tdir,
        etype="text",
        source="unit-test",
        note="test note",
        snippet="some content",
    )

    assert received == [
        {
            "eid": eid,
            "path": out_path,
            "etype": "text",
            "source": "unit-test",
        }
    ]


def test_fact_added_hook_receives_context(tmp_path: Path) -> None:
    tdir = _triage_dir(tmp_path)
    add_evidence_snippet(
        tdir=tdir,
        etype="text",
        source="seed",
        note="seed note",
        snippet="seed content",
    )
    received = []

    core.register_hook("fact.added", lambda **ctx: received.append(ctx))

    fid = add_fact(tdir=tdir, text="fact text", evidence=["E001", "E001"])

    assert received == [{"fid": fid, "text": "fact text", "evidence": ["E001"]}]


def test_hypothesis_hooks_receive_context(tmp_path: Path) -> None:
    tdir = _triage_dir(tmp_path)
    add_evidence_snippet(
        tdir=tdir,
        etype="text",
        source="seed",
        note="seed note",
        snippet="seed content",
    )
    added = []
    closed = []

    core.register_hook("hypothesis.added", lambda **ctx: added.append(ctx))
    core.register_hook("hypothesis.closed", lambda **ctx: closed.append(ctx))

    hid = add_hypothesis(
        tdir=tdir,
        hypothesis="suspect regression",
        evidence=["E001", "E001"],
        test="run repro",
        confidence="Medium",
        status="Open",
    )
    close_hypothesis(tdir=tdir, hid=hid, reason="not reproducible")

    assert added == [
        {
            "hid": hid,
            "hypothesis": "suspect regression",
            "evidence": ["E001"],
        }
    ]
    assert closed == [{"hid": hid, "reason": "not reproducible"}]


def test_validate_passed_hook_receives_context(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    tdir = _triage_dir(tmp_path)
    received = []

    core.register_hook("validate.passed", lambda **ctx: received.append(ctx))

    validate_workspace(tdir)

    assert received == [{"tdir": tdir}]
    assert "OK: validation passed" in capsys.readouterr().out


def test_validate_failed_hook_receives_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    tdir = _triage_dir(tmp_path)
    (tdir / "facts.md").write_text("F001: possible issue\n", encoding="utf-8")
    received = []

    core.register_hook("validate.failed", lambda **ctx: received.append(ctx))

    with pytest.raises(typer.Exit) as excinfo:
        validate_workspace(tdir)

    assert excinfo.value.exit_code == 2
    assert received and received[0]["tdir"] == tdir
    assert received[0]["errors"] == [
        "facts.md contains banned speculation word: possible",
        "facts.md fact 'F001' cites no EID",
    ]
    output = capsys.readouterr().out
    assert "ERROR: facts.md contains banned speculation word: possible" in output
    assert "ERROR: facts.md fact 'F001' cites no EID" in output

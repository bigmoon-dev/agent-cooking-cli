"""Tests for triageflow.rounds - run_round, helpers, deprecated fns."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from triageflow.rounds import (
    _case_set,
    _prompt_safe,
    deprecated_round0,
    deprecated_round1,
    run_round,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_profile(rounds: list, anchors=None):
    prof = {"profile_id": "test_v1", "rounds": rounds}
    if anchors is not None:
        prof["uart_anchors_default"] = anchors
    return prof


def _write_profile(tdir: Path, prof: dict) -> None:
    (tdir / "profile.yaml").write_text(yaml.safe_dump(prof), encoding="utf-8")


def _write_case(tdir: Path, data: dict) -> None:
    (tdir / "case.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")


def _read_case(tdir: Path) -> dict:
    return yaml.safe_load((tdir / "case.yaml").read_text(encoding="utf-8")) or {}


def _tdir(tmp_path: Path) -> Path:
    d = tmp_path / "triage"
    d.mkdir()
    return d


# ===========================================================================
# _case_set
# ===========================================================================


class TestCaseSet:
    def test_sets_value(self):
        d = {}
        _case_set(d, "k", "v")
        assert d == {"k": "v"}

    def test_skips_none(self):
        d = {"existing": 1}
        _case_set(d, "k", None)
        assert "k" not in d

    def test_overwrites(self):
        d = {"k": "old"}
        _case_set(d, "k", "new")
        assert d["k"] == "new"


# ===========================================================================
# _prompt_safe
# ===========================================================================


class TestPromptSafe:
    @patch("triageflow.rounds.typer.prompt", return_value="hello")
    def test_returns_value(self, mock_prompt):
        assert _prompt_safe("field") == "hello"

    @patch("triageflow.rounds.typer.prompt", return_value="")
    def test_raises_on_empty(self, mock_prompt):
        with pytest.raises(Exception):
            _prompt_safe("field")

    @patch("triageflow.rounds.typer.prompt", side_effect=EOFError)
    def test_raises_on_eof(self, mock_prompt):
        with pytest.raises(Exception):
            _prompt_safe("field")

    @patch("triageflow.rounds.typer.prompt", return_value="  spaced  ")
    def test_preserves_whitespace(self, mock_prompt):
        """_prompt_safe does NOT strip - caller is responsible."""
        assert _prompt_safe("field") == "  spaced  "

    @patch("triageflow.rounds.typer.prompt", side_effect=KeyboardInterrupt)
    def test_raises_on_keyboard_interrupt(self, mock_prompt):
        """click.Abort is raised on Ctrl-C; KeyboardInterrupt propagates."""
        with pytest.raises(KeyboardInterrupt):
            _prompt_safe("field")

    @patch("triageflow.rounds.typer.prompt", return_value="val")
    def test_default_kwarg_forwarded(self, mock_prompt):
        result = _prompt_safe("field", default="def")
        mock_prompt.assert_called_once_with("field", default="def", show_default=True)
        assert result == "val"


# ===========================================================================
# run_round - simple text fields
# ===========================================================================


class TestRunRoundSimpleFields:
    def test_symptom_field(self, tmp_path):
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 0, "fields": ["symptom"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        with patch("triageflow.rounds.typer.prompt", return_value="device reboots"):
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=True)

        case = _read_case(tdir)
        assert case["symptom"] == "device reboots"
        assert "updated_at" in case
        assert "created_at" in case

    def test_multiple_simple_fields(self, tmp_path):
        tdir = _tdir(tmp_path)
        fields = ["symptom", "impact_scope", "firmware_version", "hw_revision", "time_window"]
        prof = _make_profile([{"id": 0, "fields": fields}])
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        answers = iter(["crash", "global", "1.2.3", "revB", "last 24h"])
        with patch("triageflow.rounds.typer.prompt", side_effect=answers):
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=True)

        case = _read_case(tdir)
        assert case["symptom"] == "crash"
        assert case["impact_scope"] == "global"
        assert case["firmware_version"] == "1.2.3"
        assert case["hw_revision"] == "revB"
        assert case["time_window"] == "last 24h"

    def test_preserves_existing_created_at(self, tmp_path):
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 0, "fields": ["symptom"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {"created_at": "2024-01-01T00:00:00+00:00"})

        with patch("triageflow.rounds.typer.prompt", return_value="x"):
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=True)

        case = _read_case(tdir)
        assert case["created_at"] == "2024-01-01T00:00:00+00:00"

    def test_existing_field_used_as_default(self, tmp_path):
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 0, "fields": ["symptom"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {"symptom": "old symptom"})

        with patch("triageflow.rounds.typer.prompt", return_value="new symptom") as mock_p:
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=True)

        call_kwargs = mock_p.call_args
        assert call_kwargs[1]["default"] == "old symptom"


# ===========================================================================
# run_round - repro_steps
# ===========================================================================


class TestRunRoundReproSteps:
    def test_no_editor(self, tmp_path):
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 0, "fields": ["repro_steps"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        with patch("triageflow.rounds.typer.prompt", return_value="step1; step2"):
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=True)

        case = _read_case(tdir)
        # Value gets rstrip + newline
        assert case["repro_steps"].endswith("\n")
        assert "step1; step2" in case["repro_steps"]

    def test_with_editor(self, tmp_path):
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 0, "fields": ["repro_steps"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        with patch("triageflow.rounds.typer.edit", return_value="edited steps  \n"):
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=False)

        case = _read_case(tdir)
        assert case["repro_steps"] == "edited steps\n"

    def test_editor_returns_none_keeps_current(self, tmp_path):
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 0, "fields": ["repro_steps"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {"repro_steps": "old steps"})

        with patch("triageflow.rounds.typer.edit", return_value=None):
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=False)

        case = _read_case(tdir)
        assert "old steps" in case["repro_steps"]

    def test_no_editor_empty_repro_produces_newline(self, tmp_path):
        """When repro_steps value is falsy, it still produces a trailing newline."""
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 0, "fields": ["repro_steps"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        with patch("triageflow.rounds.typer.prompt", return_value="x"):
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=True)

        case = _read_case(tdir)
        assert case["repro_steps"].endswith("\n")

    def test_editor_empty_string_produces_newline(self, tmp_path):
        """When editor returns empty string for repro_steps, fallback to current."""
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 0, "fields": ["repro_steps"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        # typer.edit returns "" (empty) -> falsy, so `or current` kicks in
        # current is "" (nothing in case.yaml), so edited="" which is falsy ->
        # the ternary picks "\n"
        with patch("triageflow.rounds.typer.edit", return_value=""):
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=False)

        case = _read_case(tdir)
        assert case["repro_steps"] == "\n"


# ===========================================================================
# run_round - enable_more_logs_how
# ===========================================================================


class TestRunRoundEnableMoreLogsHow:
    def test_no_editor(self, tmp_path):
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 0, "fields": ["enable_more_logs_how"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        with patch("triageflow.rounds.typer.prompt", return_value="use debug flag"):
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=True)

        case = _read_case(tdir)
        assert case["enable_more_logs_how"] == "use debug flag\n"

    def test_with_editor(self, tmp_path):
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 0, "fields": ["enable_more_logs_how"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        with patch("triageflow.rounds.typer.edit", return_value="edited"):
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=False)

        case = _read_case(tdir)
        assert case["enable_more_logs_how"] == "edited\n"

    def test_editor_returns_none_keeps_current(self, tmp_path):
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 0, "fields": ["enable_more_logs_how"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {"enable_more_logs_how": "existing"})

        with patch("triageflow.rounds.typer.edit", return_value=None):
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=False)

        case = _read_case(tdir)
        assert "existing" in case["enable_more_logs_how"]

    def test_no_editor_whitespace_only_produces_newline(self, tmp_path):
        """When prompt returns whitespace-only, v is truthy so (v.rstrip()+'\\n') = '\\n'."""
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 0, "fields": ["enable_more_logs_how"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        # v="  " is truthy, v.rstrip()="" so result is ""+"\n" = "\n"
        with patch("triageflow.rounds.typer.prompt", return_value="  "):
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=True)

        case = _read_case(tdir)
        assert case["enable_more_logs_how"] == "\n"

    def test_editor_empty_string_uses_current(self, tmp_path):
        """typer.edit returns '' -> falsy -> falls back to cur."""
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 0, "fields": ["enable_more_logs_how"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {"enable_more_logs_how": "old instructions"})

        with patch("triageflow.rounds.typer.edit", return_value=""):
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=False)

        case = _read_case(tdir)
        assert "old instructions" in case["enable_more_logs_how"]


# ===========================================================================
# run_round - uart_log_format
# ===========================================================================


class TestRunRoundUartLogFormat:
    def test_strips_whitespace(self, tmp_path):
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 0, "fields": ["uart_log_format"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        with patch("triageflow.rounds.typer.prompt", return_value="  syslog  "):
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=True)

        case = _read_case(tdir)
        assert case["uart_log_format"] == "syslog"

    def test_default_is_mixed(self, tmp_path):
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 0, "fields": ["uart_log_format"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        with patch("triageflow.rounds.typer.prompt", return_value="mixed") as mock_p:
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=True)

        call_kwargs = mock_p.call_args
        assert call_kwargs[1]["default"] == "mixed"


# ===========================================================================
# run_round - can_enable_more_logs (confirm)
# ===========================================================================


class TestRunRoundCanEnableMoreLogs:
    def test_confirm_true(self, tmp_path):
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 0, "fields": ["can_enable_more_logs"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        with patch("triageflow.rounds.typer.confirm", return_value=True):
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=True)

        case = _read_case(tdir)
        assert case["can_enable_more_logs"] is True

    def test_confirm_false(self, tmp_path):
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 0, "fields": ["can_enable_more_logs"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        with patch("triageflow.rounds.typer.confirm", return_value=False):
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=True)

        case = _read_case(tdir)
        assert case["can_enable_more_logs"] is False

    def test_existing_value_used_as_default(self, tmp_path):
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 0, "fields": ["can_enable_more_logs"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {"can_enable_more_logs": True})

        with patch("triageflow.rounds.typer.confirm", return_value=True) as mock_c:
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=True)

        # Verify that the existing True value was passed as default
        mock_c.assert_called_once()
        assert mock_c.call_args[1]["default"] is True


# ===========================================================================
# run_round - capabilities (strip behavior)
# ===========================================================================


class TestRunRoundCapabilities:
    @pytest.mark.parametrize("field,answer,expected", [
        ("capabilities_phone_side", " android ", "android"),
        ("capabilities_power_measure", "multimeter ", "multimeter"),
        ("capabilities_bt_snoop", " yes", "yes"),
        ("capabilities_pmic_dump", " no ", "no"),
    ])
    def test_capability_fields_stripped(self, tmp_path, field, answer, expected):
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 0, "fields": [field]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        with patch("triageflow.rounds.typer.prompt", return_value=answer):
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=True)

        case = _read_case(tdir)
        assert case[field] == expected

    @pytest.mark.parametrize("field,default_key", [
        ("capabilities_phone_side", "unknown"),
        ("capabilities_power_measure", "unknown"),
        ("capabilities_bt_snoop", "unknown"),
        ("capabilities_pmic_dump", "unknown"),
    ])
    def test_capability_defaults_are_unknown(self, tmp_path, field, default_key):
        """When case.yaml has no existing value, default is 'unknown'."""
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 0, "fields": [field]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        with patch("triageflow.rounds.typer.prompt", return_value="unknown") as mock_p:
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=True)

        assert mock_p.call_args[1]["default"] == default_key


# ===========================================================================
# run_round - anchor_keywords
# ===========================================================================


class TestRunRoundAnchorKeywords:
    def test_user_enters_anchors(self, tmp_path):
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 0, "fields": ["anchor_keywords"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        with patch("triageflow.rounds.typer.prompt", side_effect=["error", "panic", ""]):
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=True)

        case = _read_case(tdir)
        assert case["anchor_keywords"] == ["error", "panic"]

    def test_default_anchors_from_profile(self, tmp_path):
        tdir = _tdir(tmp_path)
        prof = _make_profile(
            [{"id": 0, "fields": ["anchor_keywords"]}],
            anchors=["err", "warn", "fail"],
        )
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        with patch("triageflow.rounds.typer.prompt", side_effect=[""]):
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=True)

        case = _read_case(tdir)
        assert case["anchor_keywords"] == ["err", "warn", "fail"]

    def test_user_anchors_override_defaults(self, tmp_path):
        tdir = _tdir(tmp_path)
        prof = _make_profile(
            [{"id": 0, "fields": ["anchor_keywords"]}],
            anchors=["old1", "old2"],
        )
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        with patch("triageflow.rounds.typer.prompt", side_effect=["new1", ""]):
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=True)

        case = _read_case(tdir)
        assert case["anchor_keywords"] == ["new1"]

    def test_eof_finishes_anchor_entry(self, tmp_path):
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 0, "fields": ["anchor_keywords"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        with patch("triageflow.rounds.typer.prompt", side_effect=["kw1", EOFError]):
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=True)

        case = _read_case(tdir)
        assert case["anchor_keywords"] == ["kw1"]

    def test_existing_anchors_preserved_when_no_input(self, tmp_path):
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 0, "fields": ["anchor_keywords"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {"anchor_keywords": ["existing1", "existing2"]})

        with patch("triageflow.rounds.typer.prompt", side_effect=[""]):
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=True)

        case = _read_case(tdir)
        assert case["anchor_keywords"] == ["existing1", "existing2"]

    def test_profile_anchors_capped_at_8(self, tmp_path):
        tdir = _tdir(tmp_path)
        many = ["a" + str(i) for i in range(20)]
        prof = _make_profile(
            [{"id": 0, "fields": ["anchor_keywords"]}],
            anchors=many,
        )
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        with patch("triageflow.rounds.typer.prompt", side_effect=[""]):
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=True)

        case = _read_case(tdir)
        assert len(case["anchor_keywords"]) == 8

    def test_click_abort_finishes_anchor_entry(self, tmp_path):
        """click.Abort (Ctrl-C) also terminates anchor loop."""
        import click
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 0, "fields": ["anchor_keywords"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        with patch("triageflow.rounds.typer.prompt", side_effect=["kw1", click.Abort()]):
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=True)

        case = _read_case(tdir)
        assert case["anchor_keywords"] == ["kw1"]

    def test_anchor_whitespace_stripped(self, tmp_path):
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 0, "fields": ["anchor_keywords"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        with patch("triageflow.rounds.typer.prompt", side_effect=["  error  ", ""]):
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=True)

        case = _read_case(tdir)
        assert case["anchor_keywords"] == ["error"]

    def test_anchor_non_list_existing_treated_as_empty(self, tmp_path):
        """If anchor_keywords in case.yaml is not a list, treat as empty."""
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 0, "fields": ["anchor_keywords"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {"anchor_keywords": "not-a-list"})

        with patch("triageflow.rounds.typer.prompt", side_effect=["kw1", ""]):
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=True)

        case = _read_case(tdir)
        assert case["anchor_keywords"] == ["kw1"]


# ===========================================================================
# run_round - unknown/generic fields
# ===========================================================================


class TestRunRoundGenericField:
    def test_unknown_field_prompted(self, tmp_path):
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 0, "fields": ["custom_field"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        with patch("triageflow.rounds.typer.prompt", return_value="custom_value"):
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=True)

        case = _read_case(tdir)
        assert case["custom_field"] == "custom_value"

    def test_unknown_field_uses_existing_as_default(self, tmp_path):
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 0, "fields": ["custom_field"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {"custom_field": "old_val"})

        with patch("triageflow.rounds.typer.prompt", return_value="new_val") as mock_p:
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=True)

        assert mock_p.call_args[1]["default"] == "old_val"
        case = _read_case(tdir)
        assert case["custom_field"] == "new_val"


# ===========================================================================
# run_round - error cases
# ===========================================================================


class TestRunRoundErrors:
    def test_no_fields_for_round(self, tmp_path):
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 0, "fields": ["symptom"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        with pytest.raises(Exception, match="No fields found for round 5"):
            run_round(tdir, round_id=5, no_editor=True)

    def test_missing_profile(self, tmp_path):
        tdir = _tdir(tmp_path)
        _write_case(tdir, {})

        with pytest.raises(Exception, match="No fields found"):
            run_round(tdir, round_id=0, no_editor=True)

    def test_case_yaml_created_if_missing(self, tmp_path):
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 0, "fields": ["symptom"]}])
        _write_profile(tdir, prof)

        with patch("triageflow.rounds.typer.prompt", return_value="new"):
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=True)

        assert (tdir / "case.yaml").exists()
        case = _read_case(tdir)
        assert case["symptom"] == "new"


# ===========================================================================
# run_round - multi-round profile
# ===========================================================================


class TestRunRoundMultiRound:
    def test_round1_fields(self, tmp_path):
        tdir = _tdir(tmp_path)
        prof = _make_profile([
            {"id": 0, "fields": ["symptom"]},
            {"id": 1, "fields": ["uart_log_format", "can_enable_more_logs"]},
        ])
        _write_profile(tdir, prof)
        _write_case(tdir, {"symptom": "already filled"})

        with patch("triageflow.rounds.typer.prompt", return_value="syslog"):
            with patch("triageflow.rounds.typer.confirm", return_value=True):
                with patch("triageflow.rounds.typer.echo"):
                    run_round(tdir, round_id=1, no_editor=True)

        case = _read_case(tdir)
        assert case["uart_log_format"] == "syslog"
        assert case["can_enable_more_logs"] is True
        assert case["symptom"] == "already filled"

    def test_round0_then_round1_sequential(self, tmp_path):
        """Run round 0 then round 1 sequentially; data accumulates."""
        tdir = _tdir(tmp_path)
        prof = _make_profile([
            {"id": 0, "fields": ["symptom", "firmware_version"]},
            {"id": 1, "fields": ["uart_log_format"]},
        ])
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        # Round 0
        with patch("triageflow.rounds.typer.prompt", side_effect=["crash", "1.0"]):
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=True)

        case = _read_case(tdir)
        assert case["symptom"] == "crash"

        # Round 1
        with patch("triageflow.rounds.typer.prompt", return_value="syslog"):
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=1, no_editor=True)

        case = _read_case(tdir)
        assert case["symptom"] == "crash"
        assert case["firmware_version"] == "1.0"
        assert case["uart_log_format"] == "syslog"


# ===========================================================================
# run_round - full round with mixed field types
# ===========================================================================


class TestRunRoundFullRound:
    def test_full_round_mixed_fields(self, tmp_path):
        """A round combining prompt, confirm, editor, and anchor fields."""
        tdir = _tdir(tmp_path)
        prof = _make_profile([{
            "id": 0,
            "fields": [
                "symptom",
                "repro_steps",
                "uart_log_format",
                "can_enable_more_logs",
                "capabilities_phone_side",
                "anchor_keywords",
            ],
        }])
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        # symptom, repro_steps(no_editor), uart_log_format,
        # capabilities_phone_side, anchor("kw"), anchor("")
        prompts = iter([
            "my symptom",     # symptom
            "step 1",         # repro_steps (no_editor mode)
            "syslog",         # uart_log_format
            "android",        # capabilities_phone_side
            "kw",             # first anchor
            "",               # end anchors
        ])
        with patch("triageflow.rounds.typer.prompt", side_effect=prompts):
            with patch("triageflow.rounds.typer.confirm", return_value=True):
                with patch("triageflow.rounds.typer.echo"):
                    run_round(tdir, round_id=0, no_editor=True)

        case = _read_case(tdir)
        assert case["symptom"] == "my symptom"
        assert "step 1" in case["repro_steps"]
        assert case["uart_log_format"] == "syslog"
        assert case["can_enable_more_logs"] is True
        assert case["capabilities_phone_side"] == "android"
        assert case["anchor_keywords"] == ["kw"]


# ===========================================================================
# run_round - uart_anchors_default edge cases
# ===========================================================================


class TestRunRoundUartAnchorsDefault:
    def test_non_list_anchors_in_profile_ignored(self, tmp_path):
        """If uart_anchors_default is not a list, default_anchors stays empty."""
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 0, "fields": ["anchor_keywords"]}])
        prof["uart_anchors_default"] = "not-a-list"
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        with patch("triageflow.rounds.typer.prompt", side_effect=[""]):
            with patch("triageflow.rounds.typer.echo"):
                run_round(tdir, round_id=0, no_editor=True)

        case = _read_case(tdir)
        # No default anchors, no user input -> empty list
        assert case["anchor_keywords"] == []


# ===========================================================================
# deprecated_round0
# ===========================================================================


class TestDeprecatedRound0:
    def test_basic_no_edit(self, tmp_path):
        tdir = _tdir(tmp_path)
        _write_case(tdir, {})

        # prompt sequence: title, problem_description,
        # code_path(blank), log_path(blank), excluded_doc_path(blank)
        prompts = iter(["my title", "my description", "", "", ""])
        with patch("triageflow.rounds.typer.prompt", side_effect=prompts):
            with patch("triageflow.rounds.typer.edit", return_value="work done"):
                with patch("triageflow.rounds.typer.echo"):
                    deprecated_round0(
                        tdir,
                        case_id="CASE001",
                        title=None,
                        description=None,
                        edit=False,
                    )

        case = _read_case(tdir)
        assert case["case_id"] == "CASE001"
        assert case["title"] == "my title"

    def test_with_edit_flag(self, tmp_path):
        tdir = _tdir(tmp_path)
        _write_case(tdir, {})

        prompts = iter(["my title", "", "", ""])
        with patch("triageflow.rounds.typer.prompt", side_effect=prompts):
            with patch("triageflow.rounds.typer.edit", side_effect=["edited desc", "work"]):
                with patch("triageflow.rounds.typer.echo"):
                    deprecated_round0(
                        tdir,
                        case_id="C1",
                        title=None,
                        description=None,
                        edit=True,
                    )

        case = _read_case(tdir)
        # description gets rstrip + newline
        assert "edited desc" in case["problem_description"]

    def test_all_args_provided(self, tmp_path):
        tdir = _tdir(tmp_path)
        _write_case(tdir, {})

        # code_path(blank), log_path(blank), excluded_doc_path(blank)
        prompts = iter(["", "", ""])
        with patch("triageflow.rounds.typer.prompt", side_effect=prompts):
            with patch("triageflow.rounds.typer.edit", return_value="work"):
                with patch("triageflow.rounds.typer.echo"):
                    deprecated_round0(
                        tdir,
                        case_id="C1",
                        title="t",
                        description="d",
                        edit=False,
                    )

        case = _read_case(tdir)
        assert case["case_id"] == "C1"
        assert case["title"] == "t"

    def test_preserves_existing_created_at(self, tmp_path):
        tdir = _tdir(tmp_path)
        _write_case(tdir, {"created_at": "2024-01-01"})

        prompts = iter(["", "", ""])
        with patch("triageflow.rounds.typer.prompt", side_effect=prompts):
            with patch("triageflow.rounds.typer.edit", return_value="w"):
                with patch("triageflow.rounds.typer.echo"):
                    deprecated_round0(
                        tdir,
                        case_id="C",
                        title="t",
                        description="d",
                        edit=False,
                    )

        case = _read_case(tdir)
        assert case["created_at"] == "2024-01-01"

    def test_case_id_prompted_when_none(self, tmp_path):
        """When case_id=None, user is prompted for it."""
        tdir = _tdir(tmp_path)
        _write_case(tdir, {})

        # prompt: case_id, title, description, code_path, log_path, excluded_doc_path
        prompts = iter(["PROMPTED_ID", "title", "desc", "", "", ""])
        with patch("triageflow.rounds.typer.prompt", side_effect=prompts):
            with patch("triageflow.rounds.typer.edit", return_value="w"):
                with patch("triageflow.rounds.typer.echo"):
                    deprecated_round0(
                        tdir,
                        case_id=None,
                        title=None,
                        description=None,
                        edit=False,
                    )

        case = _read_case(tdir)
        assert case["case_id"] == "PROMPTED_ID"

    def test_edit_returns_none_uses_current(self, tmp_path):
        """When typer.edit returns None, keeps current description."""
        tdir = _tdir(tmp_path)
        _write_case(tdir, {"problem_description": "old desc"})

        prompts = iter(["title", "", "", ""])
        with patch("triageflow.rounds.typer.prompt", side_effect=prompts):
            # First edit call (description) returns None, second (work_done) returns "w"
            with patch("triageflow.rounds.typer.edit", side_effect=[None, "w"]):
                with patch("triageflow.rounds.typer.echo"):
                    deprecated_round0(
                        tdir,
                        case_id="C",
                        title=None,
                        description=None,
                        edit=True,
                    )

        case = _read_case(tdir)
        assert "old desc" in case["problem_description"]

    def test_list_prompts_collect_items(self, tmp_path):
        """code_paths, log_paths, excluded_doc_paths populated from prompt loop."""
        tdir = _tdir(tmp_path)
        _write_case(tdir, {})

        # title, code_path1, code_path2, blank, log_path1, blank, excluded1, blank
        prompts = iter(["title", "src/", "lib/", "", "logs/uart.log", "", "docs/old.md", ""])
        with patch("triageflow.rounds.typer.prompt", side_effect=prompts):
            with patch("triageflow.rounds.typer.edit", return_value="work"):
                with patch("triageflow.rounds.typer.echo"):
                    deprecated_round0(
                        tdir,
                        case_id="C1",
                        title=None,
                        description="desc",
                        edit=False,
                    )

        case = _read_case(tdir)
        assert case["code_paths"] == ["src/", "lib/"]
        assert case["log_paths"] == ["logs/uart.log"]
        assert case["excluded_doc_paths"] == ["docs/old.md"]

    def test_work_done_edit_returns_none(self, tmp_path):
        """When typer.edit for work_done returns None, keeps current."""
        tdir = _tdir(tmp_path)
        _write_case(tdir, {"work_done": "previous work"})

        prompts = iter(["", "", ""])
        with patch("triageflow.rounds.typer.prompt", side_effect=prompts):
            with patch("triageflow.rounds.typer.edit", return_value=None):
                with patch("triageflow.rounds.typer.echo"):
                    deprecated_round0(
                        tdir,
                        case_id="C",
                        title="t",
                        description="d",
                        edit=False,
                    )

        case = _read_case(tdir)
        assert "previous work" in case["work_done"]

    def test_description_none_no_edit_prompts(self, tmp_path):
        """When description=None and edit=False, user is prompted."""
        tdir = _tdir(tmp_path)
        _write_case(tdir, {})

        prompts = iter(["title", "prompted desc", "", "", ""])
        with patch("triageflow.rounds.typer.prompt", side_effect=prompts):
            with patch("triageflow.rounds.typer.edit", return_value="w"):
                with patch("triageflow.rounds.typer.echo"):
                    deprecated_round0(
                        tdir,
                        case_id="C",
                        title=None,
                        description=None,
                        edit=False,
                    )

        case = _read_case(tdir)
        assert "prompted desc" in case["problem_description"]


# ===========================================================================
# deprecated_round1
# ===========================================================================


class TestDeprecatedRound1:
    def test_basic(self, tmp_path):
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 1, "fields": ["uart_log_format"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        # prompt: uart_log_format, phone_side, power_measure, bt_snoop, pmic_dump, anchor("")
        prompts = iter(["syslog", "android", "none", "yes", "no", ""])
        with patch("triageflow.rounds.typer.prompt", side_effect=prompts):
            with patch("triageflow.rounds.typer.confirm", return_value=False):
                with patch("triageflow.rounds.typer.echo"):
                    deprecated_round1(tdir)

        case = _read_case(tdir)
        assert case["uart_log_format"] == "syslog"
        assert case["capabilities_phone_side"] == "android"
        assert case["can_enable_more_logs"] is False
        assert "updated_at" in case

    def test_with_enable_more_logs(self, tmp_path):
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 1, "fields": ["uart_log_format"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        prompts = iter(["mixed", "ios", "analyzer", "no", "yes", ""])
        with patch("triageflow.rounds.typer.prompt", side_effect=prompts):
            with patch("triageflow.rounds.typer.confirm", return_value=True):
                with patch("triageflow.rounds.typer.edit", return_value="instructions"):
                    with patch("triageflow.rounds.typer.echo"):
                        deprecated_round1(tdir)

        case = _read_case(tdir)
        assert case["can_enable_more_logs"] is True
        assert "instructions" in case["enable_more_logs_how"]

    def test_preserves_created_at(self, tmp_path):
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 1, "fields": ["uart_log_format"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {"created_at": "keep-me"})

        prompts = iter(["mixed", "unknown", "unknown", "unknown", "unknown", ""])
        with patch("triageflow.rounds.typer.prompt", side_effect=prompts):
            with patch("triageflow.rounds.typer.confirm", return_value=False):
                with patch("triageflow.rounds.typer.echo"):
                    deprecated_round1(tdir)

        case = _read_case(tdir)
        assert case["created_at"] == "keep-me"

    def test_default_anchors_from_profile(self, tmp_path):
        tdir = _tdir(tmp_path)
        prof = _make_profile(
            [{"id": 1, "fields": ["uart_log_format"]}],
            anchors=["err", "warn"],
        )
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        prompts = iter(["mixed", "unknown", "unknown", "unknown", "unknown", ""])
        with patch("triageflow.rounds.typer.prompt", side_effect=prompts):
            with patch("triageflow.rounds.typer.confirm", return_value=False):
                with patch("triageflow.rounds.typer.echo"):
                    deprecated_round1(tdir)

        case = _read_case(tdir)
        assert case["anchor_keywords"] == ["err", "warn"]

    def test_user_anchors_override_in_deprecated_round1(self, tmp_path):
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 1, "fields": ["uart_log_format"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        prompts = iter(["mixed", "unknown", "unknown", "unknown", "unknown", "myanchor", ""])
        with patch("triageflow.rounds.typer.prompt", side_effect=prompts):
            with patch("triageflow.rounds.typer.confirm", return_value=False):
                with patch("triageflow.rounds.typer.echo"):
                    deprecated_round1(tdir)

        case = _read_case(tdir)
        assert case["anchor_keywords"] == ["myanchor"]

    def test_enable_more_logs_edit_returns_none(self, tmp_path):
        """When typer.edit returns None for enable_more_logs_how, keeps current."""
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 1, "fields": ["uart_log_format"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {"enable_more_logs_how": "old instructions"})

        prompts = iter(["mixed", "unknown", "unknown", "unknown", "unknown", ""])
        with patch("triageflow.rounds.typer.prompt", side_effect=prompts):
            with patch("triageflow.rounds.typer.confirm", return_value=True):
                with patch("triageflow.rounds.typer.edit", return_value=None):
                    with patch("triageflow.rounds.typer.echo"):
                        deprecated_round1(tdir)

        case = _read_case(tdir)
        assert "old instructions" in case["enable_more_logs_how"]

    def test_non_list_anchors_in_profile_ignored(self, tmp_path):
        """uart_anchors_default that isn't a list is ignored."""
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 1, "fields": ["uart_log_format"]}])
        prof["uart_anchors_default"] = "scalar-string"
        _write_profile(tdir, prof)
        _write_case(tdir, {})

        prompts = iter(["mixed", "unknown", "unknown", "unknown", "unknown", ""])
        with patch("triageflow.rounds.typer.prompt", side_effect=prompts):
            with patch("triageflow.rounds.typer.confirm", return_value=False):
                with patch("triageflow.rounds.typer.echo"):
                    deprecated_round1(tdir)

        case = _read_case(tdir)
        # No anchors entered, no valid default -> empty list
        assert case["anchor_keywords"] == []

    def test_existing_anchors_non_list_treated_as_empty(self, tmp_path):
        """anchor_keywords in case.yaml that isn't a list -> treated as empty."""
        tdir = _tdir(tmp_path)
        prof = _make_profile([{"id": 1, "fields": ["uart_log_format"]}])
        _write_profile(tdir, prof)
        _write_case(tdir, {"anchor_keywords": "not-a-list"})

        prompts = iter(["mixed", "unknown", "unknown", "unknown", "unknown", "kw1", ""])
        with patch("triageflow.rounds.typer.prompt", side_effect=prompts):
            with patch("triageflow.rounds.typer.confirm", return_value=False):
                with patch("triageflow.rounds.typer.echo"):
                    deprecated_round1(tdir)

        case = _read_case(tdir)
        assert case["anchor_keywords"] == ["kw1"]

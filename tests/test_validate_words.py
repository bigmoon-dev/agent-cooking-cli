from pathlib import Path

from typer.testing import CliRunner

import triageflow.cli as cli


def test_validate_fails_on_speculation_word(tmp_path: Path):
    runner = CliRunner()
    root = tmp_path

    # init workspace
    res = runner.invoke(cli.app, ["--root", str(root), "init", "--profile", "embedded_system_v1"])
    assert res.exit_code == 0

    # minimal evidence
    uart = root / "uart.log"
    uart.write_text("panic\n", encoding="utf-8")
    res = runner.invoke(
        cli.app,
        [
            "--root",
            str(root),
            "evidence",
            "add-log",
            "--log-path",
            str(uart),
            "--pattern",
            "panic",
            "--before",
            "0",
            "--after",
            "0",
            "--max-matches",
            "1",
            "--note",
            "panic line",
        ],
    )
    assert res.exit_code == 0

    # grab EID
    idx = (root / "triage" / "evidence" / "index.md").read_text(encoding="utf-8")
    import re

    m = re.search(r"\b(E\d{3})\b", idx)
    assert m
    eid = m.group(1)

    # add a fact with a banned word
    res = runner.invoke(cli.app, ["--root", str(root), "facts", "add", "--text", "可能是电源问题", "--evidence", eid])
    assert res.exit_code == 0

    res = runner.invoke(cli.app, ["--root", str(root), "validate"])
    assert res.exit_code != 0

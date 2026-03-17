from __future__ import annotations

import re
import tempfile
from pathlib import Path

import typer
import yaml


def run_acceptance(app) -> None:
    """Run acceptance suite from YAML cases (workflow-driven development)."""

    from typer.testing import CliRunner

    # Keep compatible with multiple Typer versions.
    runner = CliRunner()

    def _result_output(res) -> str:
        out = getattr(res, "output", None)
        if isinstance(out, str) and out:
            return out
        stdout = getattr(res, "stdout", "")
        try:
            stderr = getattr(res, "stderr", "")
        except ValueError:
            stderr = ""
        if isinstance(stdout, str) or isinstance(stderr, str):
            return f"{stdout}{stderr}"
        return ""

    cases_dir = Path(__file__).resolve().parent / "cases"
    case_files = sorted(cases_dir.glob("*.yaml"))
    if not case_files:
        typer.echo(f"No acceptance cases found in {cases_dir}")
        raise typer.Exit(code=2)

    def _sub_vars(s: str, vars_map: dict) -> str:
        out = s
        for k, v in vars_map.items():
            out = out.replace("${" + k + "}", str(v))
        return out

    for cf in case_files:
        case = yaml.safe_load(cf.read_text(encoding="utf-8")) or {}
        if not isinstance(case, dict):
            typer.echo(f"Invalid case YAML: {cf}")
            raise typer.Exit(code=2)
        name = str(case.get("name") or cf.name)
        fixtures = case.get("fixtures") or []
        steps = case.get("steps") or []
        if not isinstance(steps, list):
            typer.echo(f"Invalid steps in {cf}")
            raise typer.Exit(code=2)

        with tempfile.TemporaryDirectory(prefix=f"triageflow-acc-{name}-") as td:
            root = Path(td)
            vars_map = {"root": str(root)}
            last_stdout = ""

            if isinstance(fixtures, list):
                for fx in fixtures:
                    if not isinstance(fx, dict):
                        continue
                    rel = str(fx.get("path") or "").strip()
                    content = str(fx.get("content") or "")
                    if not rel:
                        continue
                    p = root / rel
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(content, encoding="utf-8")

            for step in steps:
                if not isinstance(step, dict):
                    continue
                stype = str(step.get("type") or "").strip()
                if stype == "run":
                    args = step.get("args")
                    if not isinstance(args, list):
                        typer.echo(f"Invalid run args in {cf}")
                        raise typer.Exit(code=2)
                    argv = [_sub_vars(str(a), vars_map) for a in args]
                    in_raw = step.get("input")
                    input_text = None
                    if in_raw is not None:
                        input_text = _sub_vars(str(in_raw), vars_map)
                    ev = step.get("expect_exit")
                    expect_exit = int(ev) if ev is not None else 0
                    res_run = runner.invoke(app, ["--root", str(root)] + argv, input=input_text)
                    last_stdout = _result_output(res_run)
                    code = res_run.exit_code
                    if code != expect_exit:
                        typer.echo("---- command failed ----")
                        typer.echo(f"case: {name}")
                        typer.echo("argv: " + " ".join(argv))
                        typer.echo(last_stdout)
                        if res_run.exception:
                            typer.echo(str(res_run.exception))
                        typer.echo(f"Case {name} failed: expected exit {expect_exit}, got {code}")
                        raise typer.Exit(code=2)
                elif stype == "capture":
                    from_file = str(step.get("from_file") or "").strip()
                    regex = str(step.get("regex") or "").strip()
                    var = str(step.get("var") or "").strip()
                    if not (from_file and regex and var):
                        typer.echo(f"Invalid capture step in {cf}")
                        raise typer.Exit(code=2)
                    p = root / _sub_vars(from_file, vars_map)
                    txt = p.read_text(encoding="utf-8")
                    m = re.search(regex, txt)
                    if not m:
                        typer.echo(f"Case {name} capture failed: regex not found")
                        raise typer.Exit(code=2)
                    vars_map[var] = m.group(1)
                elif stype == "assert_file_contains":
                    pth = str(step.get("path") or "").strip()
                    contains = str(step.get("contains") or "")
                    if not pth:
                        typer.echo(f"Invalid assert_file_contains in {cf}")
                        raise typer.Exit(code=2)
                    p = root / _sub_vars(pth, vars_map)
                    txt = p.read_text(encoding="utf-8")
                    if contains not in txt:
                        typer.echo(f"Case {name} failed: {pth} does not contain '{contains}'")
                        raise typer.Exit(code=2)
                elif stype == "assert_file_not_contains":
                    pth = str(step.get("path") or "").strip()
                    contains = str(step.get("contains") or "")
                    if not pth:
                        typer.echo(f"Invalid assert_file_not_contains in {cf}")
                        raise typer.Exit(code=2)
                    p = root / _sub_vars(pth, vars_map)
                    txt = p.read_text(encoding="utf-8")
                    if contains in txt:
                        typer.echo(f"Case {name} failed: {pth} unexpectedly contains '{contains}'")
                        raise typer.Exit(code=2)
                elif stype == "assert_last_stdout_contains":
                    contains = str(step.get("contains") or "")
                    contains = _sub_vars(contains, vars_map)
                    if contains not in last_stdout:
                        typer.echo(f"Case {name} failed: last stdout does not contain '{contains}'")
                        typer.echo(last_stdout)
                        raise typer.Exit(code=2)
                elif stype == "delete_file":
                    pth = str(step.get("path") or "").strip()
                    if not pth:
                        typer.echo(f"Invalid delete_file in {cf}")
                        raise typer.Exit(code=2)
                    p = root / _sub_vars(pth, vars_map)
                    if p.exists():
                        p.unlink()
                elif stype == "write_file":
                    pth = str(step.get("path") or "").strip()
                    content = str(step.get("content") or "")
                    if not pth:
                        typer.echo(f"Invalid write_file in {cf}")
                        raise typer.Exit(code=2)
                    p = root / _sub_vars(pth, vars_map)
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(_sub_vars(content, vars_map), encoding="utf-8")
                else:
                    typer.echo(f"Unknown step type '{stype}' in {cf}")
                    raise typer.Exit(code=2)

    typer.echo("OK: acceptance suite passed")

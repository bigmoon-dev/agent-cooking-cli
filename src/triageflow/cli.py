from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

import typer

from .core import TRIAGE_DIRNAME, WORKSPACE
from .core import dump_yaml as _dump_yaml
from .core import load_yaml as _load_yaml
from .core import now_iso as _now_iso
from .core import read_text_if_exists as _read_text_if_exists
from .directions import build_directions as _build_directions
from .directions_ops import add_direction as _add_direction
from .directions_ops import list_directions as _list_directions
from .directions_ops import prune_directions as _prune_directions
from .document_blocks import append_block as _append_block
from .document_blocks import next_id as _next_id
from .document_blocks import split_blocks as _split_blocks
from .evidence import add_evidence_snippet as _add_evidence_snippet
from .evidence import capture_log_range as _capture_log_range
from .evidence import capture_log_windows as _capture_log_windows
from .evidence import latest_eid as _latest_eid
from .evidence import resolve_uart_log_path as _resolve_uart_log_path
from .facts_ops import add_fact as _add_fact
from .facts_ops import list_facts as _list_facts
from .facts_ops import set_fact as _set_fact
from .hypotheses_ops import add_hypothesis as _add_hypothesis
from .hypotheses_ops import close_hypothesis as _close_hypothesis
from .hypotheses_ops import list_hypotheses as _list_hypotheses
from .init_workspace import init_workspace as _init_workspace
from .profile import load_profile_yaml as _load_profile_yaml
from .profile import require_valid_profile as _require_valid_profile
from .profile_cli import list_profiles as _profile_list
from .profile_cli import show_profile as _profile_show
from .profile_cli import validate_profile as _profile_validate
from .rounds import deprecated_round0 as _deprecated_round0
from .rounds import deprecated_round1 as _deprecated_round1
from .rounds import run_round as _run_round
from .validate_rules import assert_eids_exist as _assert_eids_exist

app = typer.Typer(add_completion=False, help="Evidence-first bug triage workflow")


_WORKSPACE_ROOT: Optional[Path] = None


@app.callback()
def _global_options(
    root: Optional[Path] = typer.Option(
        None,
        "--root",
        envvar="TRIAGEFLOW_ROOT",
        help="Workspace root directory (defaults to current working directory)",
    )
) -> None:
    global _WORKSPACE_ROOT
    if root is None:
        _WORKSPACE_ROOT = None
        WORKSPACE.set_root(None)
        return
    _WORKSPACE_ROOT = Path(root).expanduser().resolve()
    WORKSPACE.set_root(_WORKSPACE_ROOT)


def _repo_root() -> Path:
    if _WORKSPACE_ROOT is not None:
        return _WORKSPACE_ROOT
    return Path.cwd()


def _triage_dir(root: Path) -> Path:
    return root / TRIAGE_DIRNAME




def _has_evidence_backed_block(text: str, header_re: str, known: set, disk: set) -> bool:
    blocks = _split_blocks(text, header_re)
    for b in blocks:
        body = "\n".join(b)
        eids = set(re.findall(r"\bE\d{3}\b", body))
        if any((e in known and e in disk) for e in eids):
            return True
    return False

@app.command()
def init(
    force: bool = typer.Option(False, help="Overwrite existing templates"),
    profile: str = typer.Option("", help="Optional profile_id (e.g. embedded_system_v1)"),
    expert: str = typer.Option("", help="Path to dianoia expert profile directory (e.g. ~/dianoia-experts/ai-product-architect)"),
) -> None:
    """Initialize triage/ workspace with templates."""

    root = _repo_root()
    tdir = _triage_dir(root)
    _init_workspace(
        tdir=tdir,
        force=force,
        profile_id=profile,
        load_profile_yaml_func=_load_profile_yaml,
        require_valid_profile_func=_require_valid_profile,
        expert_path=expert,
        workspace_root=str(root),
    )


profile_app = typer.Typer(add_completion=False)
app.add_typer(profile_app, name="profile", help="Manage profiles")


@profile_app.command("list")
def profile_list() -> None:
    """List built-in profiles."""

    _profile_list()


@profile_app.command("show")
def profile_show(profile_id: str = typer.Argument(...)) -> None:
    """Show a built-in profile YAML."""

    _profile_show(profile_id)


@profile_app.command("validate")
def profile_validate(
    profile_id: Optional[str] = typer.Argument(None, help="Built-in profile id to validate"),
    path: Optional[Path] = typer.Option(None, exists=True, dir_okay=False, help="Path to a profile.yaml to validate"),
) -> None:
    """Validate a profile (built-in or a profile.yaml file)."""

    _profile_validate(
        load_yaml_func=_load_yaml,
        repo_root_func=_repo_root,
        triage_dir_func=_triage_dir,
        profile_id=profile_id,
        path=path,
    )


round_app = typer.Typer(add_completion=False)
app.add_typer(round_app, name="round", help="Run interactive rounds")


@round_app.command("0")
def round0(
    case_id: Optional[str] = typer.Option(None, help="Case ID (optional)"),
    title: Optional[str] = typer.Option(None, help="Short title (optional)"),
    description: Optional[str] = typer.Option(None, help="Problem description (single-line; prefer --edit)"),
    edit: bool = typer.Option(True, help="Open editor to edit description"),
) -> None:
    """Round 0: collect inputs into triage/case.yaml."""

    root = _repo_root()
    tdir = _triage_dir(root)
    if not tdir.exists():
        raise typer.BadParameter("triage/ does not exist. Run: triage init")

    _deprecated_round0(
        tdir,
        case_id=case_id,
        title=title,
        description=description,
        edit=edit,
    )


@round_app.command("1")
def round1() -> None:
    """Round 1: capture capabilities + UART anchors (profile-driven if present)."""

    root = _repo_root()
    tdir = _triage_dir(root)
    if not tdir.exists():
        raise typer.BadParameter("triage/ does not exist. Run: triage init")

    _deprecated_round1(tdir)


@round_app.command("run")
def round_run(
    round_id: int = typer.Argument(..., help="Round id from profile.yaml (e.g. 0, 1)"),
    no_editor: bool = typer.Option(False, help="Do not open an editor; use prompts only"),
) -> None:
    """Run a profile-driven round (field order controlled by profile)."""

    root = _repo_root()
    tdir = _triage_dir(root)
    if not tdir.exists():
        raise typer.BadParameter("triage/ does not exist. Run: triage init")

    _run_round(tdir, round_id=round_id, no_editor=no_editor)


evidence_app = typer.Typer(add_completion=False)
app.add_typer(evidence_app, name="evidence", help="Manage evidence (EIDs)")


@evidence_app.command("attach")
def evidence_attach(
    uart_log: Optional[Path] = typer.Option(None, exists=True, dir_okay=False, help="UART log file to attach"),
) -> None:
    """Attach evidence sources to the current workspace (saves paths in case.yaml)."""

    root = _repo_root()
    tdir = _triage_dir(root)
    if not tdir.exists():
        raise typer.BadParameter("triage/ does not exist. Run: triage init")

    case_path = tdir / "case.yaml"
    data = _load_yaml(case_path)

    if uart_log is not None:
        data["uart_log_path"] = str(Path(uart_log).expanduser())

    data["updated_at"] = _now_iso()
    if "created_at" not in data:
        data["created_at"] = _now_iso()
    _dump_yaml(case_path, data)
    typer.echo(f"Wrote {case_path}")


@evidence_app.command("hunt")
def evidence_hunt(
    before: int = typer.Option(30, min=0, help="Lines of context before match"),
    after: int = typer.Option(50, min=0, help="Lines of context after match"),
    max_matches: int = typer.Option(1, min=1, help="Max matches per pattern"),
    note: str = typer.Option("anchor window", help="Note (fact only)"),
) -> None:
    """Capture evidence windows for each anchor keyword in case.yaml."""

    root = _repo_root()
    tdir = _triage_dir(root)
    if not tdir.exists():
        raise typer.BadParameter("triage/ does not exist. Run: triage init")

    case = _load_yaml(tdir / "case.yaml")
    anchors = case.get("anchor_keywords")
    if not isinstance(anchors, list) or not anchors:
        raise typer.BadParameter("No anchor_keywords found. Run: round run 1 first (or set anchor_keywords in case.yaml).")

    uart = case.get("uart_log_path")
    if not isinstance(uart, str) or not uart.strip():
        raise typer.BadParameter("No uart_log_path attached. Run: evidence attach --uart-log <file>.")

    created: List[str] = []
    summary: List[str] = []
    for a in anchors:
        pat = str(a).strip()
        if not pat:
            continue
        # Reuse add-log (pattern list)
        before_count = len(created)
        try:
            evidence_add_log(
                log_path=Path(uart),
                pattern=[pat],
                before=before,
                after=after,
                max_matches=max_matches,
                line_start=None,
                line_end=None,
                note=note,
            )
            # Collect new EIDs added by this call
            after_eid = _latest_eid(tdir)
            if after_eid and (not created or after_eid != created[-1]):
                created.append(after_eid)
        except typer.Exit:
            # No match for this anchor; continue
            continue

        if len(created) > before_count:
            summary.append(f"- {pat}: {', '.join(created[before_count:])}")

    if created:
        typer.echo("Created evidence:")
        for line in summary:
            typer.echo(line)
        typer.echo("")
        typer.echo(f"Next suggested step: facts add --text <fact> --evidence {created[0]}")
    else:
        typer.echo("No matches for any anchors")
        raise typer.Exit(code=1)


@evidence_app.command("add")
def evidence_add(
    etype: str = typer.Option(..., "--type", help="log|code|cmd"),
    source: str = typer.Option(..., help="Original source path or description"),
    note: str = typer.Option(..., help="What it shows (fact only)"),
    content: Optional[str] = typer.Option(None, help="Inline snippet content"),
    content_file: Optional[Path] = typer.Option(None, exists=True, dir_okay=False, help="File containing snippet"),
) -> None:
    """Add an evidence snippet and register an EID."""

    etype_norm = etype.strip().lower()

    root = _repo_root()
    tdir = _triage_dir(root)
    if not tdir.exists():
        raise typer.BadParameter("triage/ does not exist. Run: triage init")

    snippet = ""
    if content_file is not None:
        snippet = content_file.read_text(encoding="utf-8")
    elif content is not None:
        snippet = content
    else:
        snippet = typer.edit("") or ""

    eid, out_path = _add_evidence_snippet(tdir=tdir, etype=etype_norm, source=source, note=note, snippet=snippet)
    typer.echo(f"Added {eid}: {out_path}")


@evidence_app.command("add-text")
def evidence_add_text(
    source: str = typer.Option("", help="Source description (optional)"),
    note: str = typer.Option(..., help="What it shows (fact only)"),
    content: Optional[str] = typer.Option(None, help="Inline text content"),
    content_file: Optional[Path] = typer.Option(None, exists=True, dir_okay=False, help="File containing text"),
) -> None:
    """Add a generic text evidence snippet (stored under evidence/cmd)."""

    src = source.strip() or "text"
    evidence_add(
        etype="text",
        source=src,
        note=note,
        content=content,
        content_file=content_file,
    )


@evidence_app.command("add-log")
def evidence_add_log(
    log_path: Optional[Path] = typer.Option(None, exists=True, dir_okay=False, help="Log file path (optional if attached)"),
    pattern: List[str] = typer.Option(..., "--pattern", help="Regex pattern to match; can be repeated"),
    before: int = typer.Option(20, min=0, help="Lines of context before match"),
    after: int = typer.Option(20, min=0, help="Lines of context after match"),
    max_matches: int = typer.Option(3, min=1, help="Max matches to capture"),
    line_start: Optional[int] = typer.Option(None, min=1, help="Capture a fixed line range (start, 1-based)"),
    line_end: Optional[int] = typer.Option(None, min=1, help="Capture a fixed line range (end, 1-based, inclusive)"),
    note: str = typer.Option("matched pattern", help="Note (fact only)"),
) -> None:
    """Capture log context windows around regex matches as evidence."""

    root = _repo_root()
    tdir = _triage_dir(root)
    if not tdir.exists():
        raise typer.BadParameter("triage/ does not exist. Run: triage init")

    if log_path is None:
        log_path = _resolve_uart_log_path(tdir)
    if log_path is None:
        raise typer.BadParameter("--log-path is required (or attach uart_log_path via: evidence attach --uart-log <file>)")

    if line_start is not None or line_end is not None:
        if line_start is None or line_end is None:
            raise typer.BadParameter("--line-start and --line-end must be provided together")

        eid, out_path = _capture_log_range(
            tdir=tdir,
            log_path=log_path,
            line_start=int(line_start),
            line_end=int(line_end),
            note=note,
        )
        typer.echo(f"Added {eid}: {out_path}")
        return

    created = _capture_log_windows(
        tdir=tdir,
        log_path=log_path,
        pattern=list(pattern),
        before=before,
        after=after,
        max_matches=max_matches,
        note=note,
    )
    if not created:
        raise typer.Exit(code=1)
    # Keep stdout stable for existing acceptance tests.
    for eid in created:
        typer.echo(f"Added {eid}: {tdir / 'evidence' / 'log' / f'{eid}_log.txt'}")


def _collect_eids_from_file(path: Path) -> set[str]:
    text = _read_text_if_exists(path)
    return set(re.findall(r"\bE\d{3}\b", text))


@app.command()
def validate() -> None:
    """Validate hard rules (evidence citations, no speculation in facts)."""

    root = _repo_root()
    tdir = _triage_dir(root)
    if not tdir.exists():
        raise typer.BadParameter("triage/ does not exist. Run: triage init")

    from .validate import validate_workspace

    validate_workspace(tdir)


facts_app = typer.Typer(add_completion=False)
app.add_typer(facts_app, name="facts", help="Manage facts (avoid manual edits)")


@facts_app.command("add")
def facts_add(
    text: str = typer.Option(..., help="Fact text (no speculation)"),
    evidence: List[str] = typer.Option(..., "--evidence", help="Evidence IDs (repeatable, E###)"),
) -> None:
    root = _repo_root()
    tdir = _triage_dir(root)
    if not tdir.exists():
        raise typer.BadParameter("triage/ does not exist. Run: triage init")

    fid = _add_fact(tdir=tdir, text=text, evidence=evidence)
    typer.echo(f"Added {fid} to {tdir / 'facts.md'}")


@facts_app.command("list")
def facts_list() -> None:
    root = _repo_root()
    tdir = _triage_dir(root)
    for line in _list_facts(tdir=tdir):
        typer.echo(line)


@facts_app.command("set")
def facts_set(
    fid: str = typer.Option(..., "--id", help="Fact id (F###)"),
    text: str = typer.Option(..., help="Fact text (no speculation)"),
    evidence: List[str] = typer.Option(..., "--evidence", help="Evidence IDs (repeatable, E###)"),
) -> None:
    root = _repo_root()
    tdir = _triage_dir(root)
    if not tdir.exists():
        raise typer.BadParameter("triage/ does not exist. Run: triage init")

    _set_fact(tdir=tdir, fid=fid, text=text, evidence=evidence)
    typer.echo(f"Updated {fid.strip().upper()} in {tdir / 'facts.md'}")


hyp_app = typer.Typer(add_completion=False)
app.add_typer(hyp_app, name="hypotheses", help="Manage hypotheses (avoid manual edits)")


@hyp_app.command("add")
def hypotheses_add(
    hypothesis: str = typer.Option(..., help="Hypothesis statement"),
    evidence: List[str] = typer.Option(..., "--evidence", help="Evidence IDs (repeatable, E###)"),
    test: str = typer.Option("", help="Discriminative test idea"),
    confidence: str = typer.Option("Medium", help="Low|Medium|High"),
    status: str = typer.Option("Open", help="Open|Closed"),
) -> None:
    root = _repo_root()
    tdir = _triage_dir(root)
    if not tdir.exists():
        raise typer.BadParameter("triage/ does not exist. Run: triage init")

    hid = _add_hypothesis(
        tdir=tdir,
        hypothesis=hypothesis,
        evidence=evidence,
        test=test,
        confidence=confidence,
        status=status,
    )
    typer.echo(f"Added {hid} to {tdir / 'hypotheses.md'}")


@hyp_app.command("list")
def hypotheses_list() -> None:
    root = _repo_root()
    tdir = _triage_dir(root)
    for line in _list_hypotheses(tdir=tdir):
        typer.echo(line)


@hyp_app.command("close")
def hypotheses_close(
    hid: str = typer.Option(..., "--id", help="Hypothesis id (H###)"),
    reason: str = typer.Option("", help="Why closed (fact only)"),
) -> None:
    root = _repo_root()
    tdir = _triage_dir(root)
    _close_hypothesis(tdir=tdir, hid=hid, reason=reason)
    typer.echo(f"Closed {hid.strip().upper()} in {tdir / 'hypotheses.md'}")


dir_app = typer.Typer(add_completion=False)
app.add_typer(dir_app, name="directions", help="Manage directions (avoid manual edits)")


@dir_app.command("add")
def directions_add(
    direction: str = typer.Option(..., help="Direction (component/chain area)"),
    evidence: List[str] = typer.Option(..., "--evidence", help="Evidence IDs (repeatable, E###)"),
    next_test: str = typer.Option("", help="Next minimal discriminative test"),
    falsify_if: str = typer.Option("", help="Falsify condition"),
    confidence: str = typer.Option("Medium", help="Low|Medium|High"),
) -> None:
    root = _repo_root()
    tdir = _triage_dir(root)
    if not tdir.exists():
        raise typer.BadParameter("triage/ does not exist. Run: triage init")

    did = _add_direction(
        tdir=tdir,
        direction=direction,
        evidence=evidence,
        next_test=next_test,
        falsify_if=falsify_if,
        confidence=confidence,
    )
    typer.echo(f"Added {did} to {tdir / 'directions.md'}")


@dir_app.command("list")
def directions_list() -> None:
    root = _repo_root()
    tdir = _triage_dir(root)
    for line in _list_directions(tdir=tdir):
        typer.echo(line)


@dir_app.command("prune")
def directions_prune(
    top_n: int = typer.Option(3, min=1, max=10, help="Keep only first N direction blocks"),
) -> None:
    root = _repo_root()
    tdir = _triage_dir(root)
    _prune_directions(tdir=tdir, top_n=top_n)
    typer.echo(f"Pruned directions to top {top_n} in {tdir / 'directions.md'}")


exp_app = typer.Typer(add_completion=False)
app.add_typer(exp_app, name="experiments", help="Manage experiments (avoid manual edits)")


@exp_app.command("add")
def experiments_add(
    goal: str = typer.Option(..., help="Goal"),
    steps: str = typer.Option("", help="Steps"),
    expected: str = typer.Option("", help="Expected"),
    observed: str = typer.Option("", help="Observed"),
    evidence: List[str] = typer.Option([], "--evidence", help="Evidence produced (repeatable, E###)"),
    conclusion: str = typer.Option("", help="Conclusion"),
) -> None:
    root = _repo_root()
    tdir = _triage_dir(root)
    if not tdir.exists():
        raise typer.BadParameter("triage/ does not exist. Run: triage init")

    eids = [e.strip().upper() for e in evidence if e.strip()]
    for e in eids:
        if not re.fullmatch(r"E\d{3}", e):
            raise typer.BadParameter(f"Invalid evidence id: {e}")
    if eids:
        _assert_eids_exist(tdir, eids)

    exp_path = tdir / "experiments.md"
    xid = _next_id(exp_path, "X")
    block = (
        f"{xid}\n"
        f"Goal: {goal.strip()}\n"
        + (f"Steps: {steps.strip()}\n" if steps.strip() else "Steps:\n")
        + (f"Expected: {expected.strip()}\n" if expected.strip() else "Expected:\n")
        + (f"Observed: {observed.strip()}\n" if observed.strip() else "Observed:\n")
        + (f"Evidence produced: ({', '.join(sorted(set(eids)))})\n" if eids else "Evidence produced: ()\n")
        + (f"Conclusion: {conclusion.strip()}\n" if conclusion.strip() else "Conclusion:\n")
    )
    _append_block(exp_path, block)
    typer.echo(f"Added {xid} to {exp_path}")


excl_app = typer.Typer(add_completion=False)
app.add_typer(excl_app, name="excluded", help="Manage exclusions (avoid manual edits)")


@excl_app.command("add")
def excluded_add(
    suspect: str = typer.Option(..., help="What is excluded"),
    because: str = typer.Option(..., help="Why excluded (fact only)"),
    evidence: List[str] = typer.Option(..., "--evidence", help="Evidence IDs (repeatable, E###)"),
    experiment: str = typer.Option("", help="Experiment id (e.g. X001)"),
    residual_risk: str = typer.Option("", help="Residual risk"),
) -> None:
    root = _repo_root()
    tdir = _triage_dir(root)
    if not tdir.exists():
        raise typer.BadParameter("triage/ does not exist. Run: triage init")

    eids = [e.strip().upper() for e in evidence if e.strip()]
    if not eids:
        raise typer.BadParameter("At least one --evidence E### is required")
    for e in eids:
        if not re.fullmatch(r"E\d{3}", e):
            raise typer.BadParameter(f"Invalid evidence id: {e}")
    _assert_eids_exist(tdir, eids)

    ex_path = tdir / "excluded.md"
    sid = _next_id(ex_path, "S")
    block = (
        f"{sid}: {suspect.strip()}\n"
        f"Excluded because: {because.strip()} ({', '.join(sorted(set(eids)))})\n"
        + (f"Experiment: {experiment.strip()}\n" if experiment.strip() else "Experiment: \n")
        + (f"Residual risk: {residual_risk.strip()}\n" if residual_risk.strip() else "Residual risk: \n")
    )
    _append_block(ex_path, block)
    typer.echo(f"Added {sid} to {ex_path}")


@app.command()
def status() -> None:
    """Print a compact digest for agents (keeps context small)."""

    root = _repo_root()
    tdir = _triage_dir(root)
    if not tdir.exists():
        raise typer.BadParameter("triage/ does not exist. Run: triage init")

    from .status_view import print_status

    print_status(tdir)


@app.command("direction-build")
def direction_build(
    top_n: int = typer.Option(3, min=1, max=5, help="Number of directions to keep"),
    overwrite: bool = typer.Option(False, help="Overwrite directions.md if it exists"),
    force_overwrite: bool = typer.Option(
        False, "--force-overwrite",
        help="Force overwrite even for design-imported directions (NOT RECOMMENDED)",
    ),
) -> None:
    """Build Top directions from evidence-backed hypotheses (MVP scoring)."""

    root = _repo_root()
    tdir = _triage_dir(root)
    if not tdir.exists():
        raise typer.BadParameter("triage/ does not exist. Run: triage init")

    _build_directions(tdir=tdir, top_n=top_n, overwrite=overwrite,
                      force_overwrite=force_overwrite)


@app.command("next")
def next_steps() -> None:
    """Print the recommended golden-path next command based on workspace state."""

    root = _repo_root()
    tdir = _triage_dir(root)
    if not tdir.exists():
        typer.echo("Next: init")
        raise typer.Exit(code=0)

    from .navigator import print_next

    print_next(tdir)


@app.command("start")
def start(
    profile: str = typer.Option(..., help="Profile id (e.g. embedded_system_v1)"),
) -> None:
    """Start a workflow: init + print next."""

    init(profile=profile)
    next_steps()


def main() -> None:
    app()


acceptance_app = typer.Typer(add_completion=False)
app.add_typer(acceptance_app, name="acceptance", help="Acceptance checks (developer workflow)")


@acceptance_app.command("run")
def acceptance_run() -> None:
    """Run acceptance suite from YAML cases (workflow-driven development)."""

    from .acceptance.runner import run_acceptance

    run_acceptance(app)


if __name__ == "__main__":
    main()

from __future__ import annotations

import datetime as _dt
import os
import re
import tempfile
from pathlib import Path
from typing import List, Optional

import click
import typer
import yaml


app = typer.Typer(add_completion=False, help="Evidence-first bug triage workflow")


TRIAGE_DIRNAME = "triage"

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
        return
    _WORKSPACE_ROOT = Path(root).expanduser().resolve()


def _profiles_dir() -> Path:
    return Path(__file__).resolve().parent / "profiles"


def _load_profile_yaml(profile_id: str) -> dict:
    pid = profile_id.strip()
    if not pid:
        raise typer.BadParameter("profile_id is required")
    p = _profiles_dir() / f"{pid}.yaml"
    if not p.exists():
        raise typer.BadParameter(f"Unknown profile_id '{pid}'. Expected file: {p}")
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise typer.BadParameter(f"Invalid profile YAML: {p}")
    return data


def _load_active_profile(triage_dir: Path) -> dict:
    """Load triage/profile.yaml if present; else return empty."""

    p = triage_dir / "profile.yaml"
    if not p.exists():
        return {}
    return _load_yaml(p)


def _repo_root() -> Path:
    if _WORKSPACE_ROOT is not None:
        return _WORKSPACE_ROOT
    return Path.cwd()


def _triage_dir(root: Path) -> Path:
    return root / TRIAGE_DIRNAME


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    _ensure_parent(path)
    path.write_text(content, encoding="utf-8")


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise typer.BadParameter(f"Expected mapping YAML in {path}")
    return data


def _dump_yaml(path: Path, data: dict) -> None:
    _ensure_parent(path)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=False)


def _parse_existing_eids(index_md: str) -> list[int]:
    # E001, E002, ...
    nums: list[int] = []
    for m in re.finditer(r"\bE(\d{3})\b", index_md):
        nums.append(int(m.group(1)))
    return nums


def _next_eid(triage_dir: Path) -> str:
    index_path = triage_dir / "evidence" / "index.md"
    existing = _parse_existing_eids(_read_text_if_exists(index_path))
    n = (max(existing) + 1) if existing else 1
    return f"E{n:03d}"


def _append_evidence_index(triage_dir: Path, *, eid: str, etype: str, source: str, note: str) -> None:
    index_path = triage_dir / "evidence" / "index.md"
    text = _read_text_if_exists(index_path)
    if not text.strip():
        text = (
            "| Evidence ID | Type | Source | Time | What it shows (fact only) |\n"
            "|---|---|---|---|---|\n"
        )
    line = f"| {eid} | {etype} | {source} | {_now_iso()} | {note} |\n"
    _write_text(index_path, text + line)


def _parse_evidence_index(triage_dir: Path) -> dict[str, dict[str, str]]:
    """Return mapping of EID -> {type, source, note} from evidence/index.md."""

    index_path = triage_dir / "evidence" / "index.md"
    text = _read_text_if_exists(index_path)
    info: dict[str, dict[str, str]] = {}
    for line in text.splitlines():
        # | E001 | log | logs/app.log:L10-L20 | ... | note |
        if not line.startswith("|"):
            continue
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) < 5:
            continue
        eid = cols[0]
        if not re.fullmatch(r"E\d{3}", eid):
            continue
        info[eid] = {"type": cols[1], "source": cols[2], "note": cols[4]}
    return info


def _evidence_files_on_disk(triage_dir: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    ev_dir = triage_dir / "evidence"
    if not ev_dir.exists():
        return out
    for sub in ("log", "code", "cmd"):
        d = ev_dir / sub
        if not d.exists():
            continue
        for p in d.glob("E[0-9][0-9][0-9]_*.txt"):
            m = re.match(r"^(E\d{3})_", p.name)
            if not m:
                continue
            out[m.group(1)] = p
    return out


def _known_eids(triage_dir: Path) -> set[str]:
    index_text = _read_text_if_exists(triage_dir / "evidence" / "index.md")
    return set(re.findall(r"\bE\d{3}\b", index_text))


def _latest_eid(triage_dir: Path) -> Optional[str]:
    index_text = _read_text_if_exists(triage_dir / "evidence" / "index.md")
    eids = re.findall(r"\bE\d{3}\b", index_text)
    if not eids:
        return None
    # Preserve order of appearance, pick the last.
    return list(dict.fromkeys(eids))[-1]


def _has_evidence_backed_block(text: str, header_re: str, known: set, disk: set) -> bool:
    blocks = _split_blocks(text, header_re)
    for b in blocks:
        body = "\n".join(b)
        eids = set(re.findall(r"\bE\d{3}\b", body))
        if any((e in known and e in disk) for e in eids):
            return True
    return False


def _has_real_hypothesis(triage_dir: Path) -> bool:
    known = _known_eids(triage_dir)
    disk = set(_evidence_files_on_disk(triage_dir).keys())
    hyp_text = _read_text_if_exists(triage_dir / "hypotheses.md")
    blocks = _split_blocks(hyp_text, r"^H\d{3}\b.*")
    for b in blocks:
        body = "\n".join(b)
        eids = set(re.findall(r"\bE\d{3}\b", body))
        if not any((e in known and e in disk) for e in eids):
            continue
        # Template has empty "Hypothesis:". Require substantive content.
        if re.search(r"^Hypothesis:\s*\S", body, flags=re.MULTILINE):
            return True
    return False


def _has_generated_directions(triage_dir: Path) -> bool:
    known = _known_eids(triage_dir)
    disk = set(_evidence_files_on_disk(triage_dir).keys())
    dtext = _read_text_if_exists(triage_dir / "directions.md")
    blocks = _split_blocks(dtext, r"^DIR-\d+\b.*")
    for b in blocks:
        header = b[0] if b else ""
        body = "\n".join(b)
        eids = set(re.findall(r"\bE\d{3}\b", body))
        if not any((e in known and e in disk) for e in eids):
            continue
        # Template directions don't have "From: H###" in header.
        if re.search(r"\bFrom:\s*H\d{3}\b", header):
            return True
    return False


def _assert_eids_exist(triage_dir: Path, eids: List[str]) -> None:
    known = _known_eids(triage_dir)
    disk = set(_evidence_files_on_disk(triage_dir).keys())
    missing = [e for e in eids if e not in known]
    missing_files = [e for e in eids if e not in disk]
    if missing:
        raise typer.BadParameter(f"Unknown EIDs (not in evidence/index.md): {', '.join(missing)}")
    if missing_files:
        raise typer.BadParameter(f"EIDs missing evidence files on disk: {', '.join(missing_files)}")


def _next_id(path: Path, prefix: str) -> str:
    text = _read_text_if_exists(path)
    nums: list[int] = []
    for m in re.finditer(rf"\b{re.escape(prefix)}(\d{{3}})\b", text):
        nums.append(int(m.group(1)))
    n = (max(nums) + 1) if nums else 1
    return f"{prefix}{n:03d}"


def _append_block(path: Path, block: str) -> None:
    prev = _read_text_if_exists(path)
    if prev and not prev.endswith("\n"):
        prev += "\n"
    if prev and not prev.endswith("\n\n"):
        prev += "\n"
    _write_text(path, prev + block.rstrip() + "\n")


def _split_blocks(text: str, header_re: str) -> List[List[str]]:
    lines = text.splitlines()
    hpat = re.compile(header_re)
    blocks: List[List[str]] = []
    cur: List[str] = []
    for line in lines:
        if hpat.match(line):
            if cur:
                blocks.append(cur)
            cur = [line]
        else:
            if cur:
                cur.append(line)
    if cur:
        blocks.append(cur)
    return blocks


def _join_blocks(blocks: List[List[str]]) -> str:
    out_lines: List[str] = []
    for b in blocks:
        if not b:
            continue
        out_lines.extend(b)
        if out_lines and out_lines[-1].strip() != "":
            out_lines.append("")
        else:
            out_lines.append("")
    return "\n".join(out_lines).rstrip() + "\n"


def _infer_triage_templates() -> dict[str, str]:
    # Keep templates minimal; agents fill them.
    return {
        "case.yaml": (
            "case_id: \"\"\n"
            "title: \"\"\n"
            "problem_description: |\n"
            "  \n"
            "code_paths: []\n"
            "log_paths: []\n"
            "work_done: |\n"
            "  \n"
            "excluded_doc_paths: []\n"
            "constraints:\n"
            "  - \"Every hypothesis must cite code or log evidence\"\n"
            "  - \"No imagination; evidence-first\"\n"
        ),
        "facts.md": (
            "# Facts\n\n"
            "Rules:\n"
            "- Facts only; avoid speculation wording.\n"
            "- Each fact cites evidence IDs like (E001).\n\n"
            "F001: \n"
        ),
        "hypotheses.md": (
            "# Hypotheses\n\n"
            "Rules:\n"
            "- Each hypothesis MUST cite at least one evidence ID (E###).\n"
            "- No evidence -> move to leads.md (does not participate in direction ranking).\n\n"
            "H001 (Status: Open | Confidence: Medium)\n"
            "Hypothesis: \n"
            "Evidence: (E001)\n"
            "Test: \n\n"
        ),
        "directions.md": (
            "# Directions\n\n"
            "Rules:\n"
            "- Keep top 1-3 directions only.\n"
            "- Each direction MUST cite evidence IDs (E###).\n\n"
            "DIR-1 (Confidence: Medium)\n"
            "Direction: \n"
            "Explains: (F001)\n"
            "Evidence chain: (E001)\n"
            "Next minimal test: \n"
            "Falsify if: \n\n"
        ),
        "experiments.md": (
            "# Experiments\n\n"
            "X001\n"
            "Goal: \n"
            "Steps:\n"
            "Expected:\n"
            "Observed:\n"
            "Evidence produced: (E001)\n"
            "Conclusion: \n\n"
        ),
        "excluded.md": (
            "# Excluded Suspects\n\n"
            "S001: \n"
            "Excluded because: (E001)\n"
            "Experiment: (X001)\n"
            "Residual risk: \n\n"
        ),
        "leads.md": (
            "# Leads (Not hypotheses)\n\n"
            "Only store leads that still have some evidence.\n\n"
        ),
        os.path.join("evidence", "index.md"): (
            "| Evidence ID | Type | Source | Time | What it shows (fact only) |\n"
            "|---|---|---|---|---|\n"
        ),
    }


@app.command()
def init(
    force: bool = typer.Option(False, help="Overwrite existing templates"),
    profile: str = typer.Option("", help="Optional profile_id (e.g. embedded_system_v1)"),
) -> None:
    """Initialize triage/ workspace with templates."""

    root = _repo_root()
    tdir = _triage_dir(root)
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / "evidence" / "log").mkdir(parents=True, exist_ok=True)
    (tdir / "evidence" / "code").mkdir(parents=True, exist_ok=True)
    (tdir / "evidence" / "cmd").mkdir(parents=True, exist_ok=True)

    templates = _infer_triage_templates()
    created = 0
    skipped = 0
    for rel, content in templates.items():
        path = tdir / rel
        if path.exists() and not force:
            skipped += 1
            continue
        _write_text(path, content)
        created += 1

    if profile.strip():
        prof = _load_profile_yaml(profile.strip())
        prof_path = tdir / "profile.yaml"
        if (not prof_path.exists()) or force:
            _dump_yaml(prof_path, prof)
            typer.echo(f"Wrote {prof_path}")
        else:
            typer.echo(f"Skipped existing {prof_path} (use --force to overwrite)")

    typer.echo(f"Initialized {tdir} (created={created}, skipped={skipped})")


profile_app = typer.Typer(add_completion=False)
app.add_typer(profile_app, name="profile", help="Manage profiles")


@profile_app.command("list")
def profile_list() -> None:
    """List built-in profiles."""

    d = _profiles_dir()
    if not d.exists():
        typer.echo("No profiles directory")
        raise typer.Exit(code=1)
    profs = sorted([p.stem for p in d.glob("*.yaml")])
    for p in profs:
        typer.echo(p)


@profile_app.command("show")
def profile_show(profile_id: str = typer.Argument(...)) -> None:
    """Show a built-in profile YAML."""

    prof = _load_profile_yaml(profile_id)
    typer.echo(yaml.safe_dump(prof, sort_keys=False, allow_unicode=False))


round_app = typer.Typer(add_completion=False)
app.add_typer(round_app, name="round", help="Run interactive rounds")


def _get_profile_round_fields(profile: dict, round_id: int) -> List[str]:
    rounds = profile.get("rounds")
    if not isinstance(rounds, list):
        return []
    for r in rounds:
        if not isinstance(r, dict):
            continue
        if r.get("id") == round_id:
            fields = r.get("fields")
            if isinstance(fields, list):
                return [str(x) for x in fields]
    return []


def _profile_required_evidence(profile: dict) -> List[str]:
    v = profile.get("required_evidence")
    if isinstance(v, list):
        return [str(x) for x in v]
    return []


def _is_missing_case_field(case: dict, key: str) -> bool:
    if key not in case:
        return True
    v = case.get(key)
    if v is None:
        return True
    if isinstance(v, str):
        return not v.strip()
    if isinstance(v, list):
        return len(v) == 0
    # bool/number/dict treated as present
    return False


def _case_set(data: dict, key: str, value) -> None:
    if value is None:
        return
    data[key] = value


def _prompt_safe(text: str, *, default: str = "", show_default: bool = True) -> str:
    try:
        v = str(typer.prompt(text, default=default, show_default=show_default))
        if v == "":
            raise typer.BadParameter("Input exhausted (empty). Provide all required lines or run interactively.")
        return v
    except (EOFError, click.Abort):
        raise typer.BadParameter("Input exhausted (non-interactive stdin). Provide --no-editor input or run interactively.")


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

    case_path = tdir / "case.yaml"
    data = _load_yaml(case_path)

    if case_id is None:
        default = data.get("case_id") or _dt.date.today().strftime("%Y%m%d")
        case_id = typer.prompt("case_id", default=default)
    if title is None:
        title = typer.prompt("title", default=str(data.get("title") or ""))

    if edit:
        current_desc = data.get("problem_description") or description or ""
        edited = typer.edit(current_desc)
        if edited is None:
            edited = current_desc
        description_final = edited.rstrip() + "\n"
    else:
        if description is None:
            description = typer.prompt("problem_description", default=str(data.get("problem_description") or ""))
        description_final = (description or "").rstrip() + "\n"

    def _prompt_list(name: str, current: List[str]) -> List[str]:
        typer.echo(f"Enter {name} one per line; blank line to finish.")
        items: List[str] = []
        if current:
            typer.echo(f"Current {name}: {current}")
        while True:
            s = typer.prompt(name, default="", show_default=False)
            s = s.strip()
            if not s:
                break
            items.append(s)
        return items or current

    code_paths = _prompt_list("code_path", list(data.get("code_paths") or []))
    log_paths = _prompt_list("log_path", list(data.get("log_paths") or []))
    excluded_doc_paths = _prompt_list("excluded_doc_path", list(data.get("excluded_doc_paths") or []))

    typer.echo("Enter work_done (opens editor).")
    current_work = data.get("work_done") or ""
    work_done = typer.edit(current_work) or current_work

    data.update(
        {
            "case_id": case_id,
            "title": title,
            "problem_description": description_final,
            "code_paths": code_paths,
            "log_paths": log_paths,
            "work_done": (work_done.rstrip() + "\n") if work_done else "\n",
            "excluded_doc_paths": excluded_doc_paths,
            "updated_at": _now_iso(),
        }
    )
    if "created_at" not in data:
        data["created_at"] = _now_iso()

    _dump_yaml(case_path, data)
    typer.echo(f"Wrote {case_path}")

    typer.echo("NOTE: 'round 0' is deprecated. Use: round run 0")


@round_app.command("1")
def round1() -> None:
    """Round 1: capture capabilities + UART anchors (profile-driven if present)."""

    root = _repo_root()
    tdir = _triage_dir(root)
    if not tdir.exists():
        raise typer.BadParameter("triage/ does not exist. Run: triage init")

    case_path = tdir / "case.yaml"
    data = _load_yaml(case_path)
    prof = _load_active_profile(tdir)
    default_anchors: List[str] = []
    prof_anchors = prof.get("uart_anchors_default")
    if isinstance(prof_anchors, list):
        default_anchors = [str(x) for x in prof_anchors]

    typer.echo("UART log format (best effort):")
    uart_log_format = typer.prompt(
        "uart_log_format",
        default=str(data.get("uart_log_format") or "mixed"),
        show_default=True,
    ).strip()

    can_enable_more_logs = typer.confirm(
        "Can you enable more detailed UART logs (power/bt/charger)?",
        default=bool(data.get("can_enable_more_logs") or False),
    )
    enable_more_logs_how = str(data.get("enable_more_logs_how") or "")
    if can_enable_more_logs:
        enable_more_logs_how = typer.edit(enable_more_logs_how) or enable_more_logs_how

    phone_side = typer.prompt(
        "phone_side (android/ios/none/unknown)",
        default=str(data.get("capabilities_phone_side") or "unknown"),
    ).strip()
    power_measure = typer.prompt(
        "power_measure (none/multimeter/analyzer/onboard/unknown)",
        default=str(data.get("capabilities_power_measure") or "unknown"),
    ).strip()
    bt_snoop = typer.prompt(
        "bt_snoop (yes/no/unknown)",
        default=str(data.get("capabilities_bt_snoop") or "unknown"),
    ).strip()
    pmic_dump = typer.prompt(
        "pmic_dump (yes/no/unknown)",
        default=str(data.get("capabilities_pmic_dump") or "unknown"),
    ).strip()

    anchor_current = data.get("anchor_keywords")
    anchors: List[str]
    if isinstance(anchor_current, list):
        anchors = [str(x) for x in anchor_current]
    else:
        anchors = []
    if not anchors and default_anchors:
        anchors = default_anchors[:8]

    typer.echo("Enter anchor keywords (one per line; blank line to finish).")
    typer.echo("These are used to locate high-signal windows in UART logs.")
    if anchors:
        typer.echo(f"Current anchors: {anchors}")
    new_anchors: List[str] = []
    while True:
        s = typer.prompt("anchor", default="", show_default=False).strip()
        if not s:
            break
        new_anchors.append(s)
    if new_anchors:
        anchors = new_anchors

    data.update(
        {
            "uart_log_format": uart_log_format,
            "can_enable_more_logs": bool(can_enable_more_logs),
            "enable_more_logs_how": (enable_more_logs_how.rstrip() + "\n") if enable_more_logs_how else "",
            "capabilities_phone_side": phone_side,
            "capabilities_power_measure": power_measure,
            "capabilities_bt_snoop": bt_snoop,
            "capabilities_pmic_dump": pmic_dump,
            "anchor_keywords": anchors,
            "updated_at": _now_iso(),
        }
    )
    if "created_at" not in data:
        data["created_at"] = _now_iso()
    _dump_yaml(case_path, data)
    typer.echo(f"Wrote {case_path}")

    typer.echo("NOTE: 'round 1' is deprecated. Use: round run 1")


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

    prof = _load_active_profile(tdir)
    fields = _get_profile_round_fields(prof, round_id)
    if not fields:
        raise typer.BadParameter(f"No fields found for round {round_id}. Check triage/profile.yaml")

    case_path = tdir / "case.yaml"
    data = _load_yaml(case_path)

    # Reuse existing round0/round1 implementations where possible,
    # but allow profile to choose which prompts to include.
    # This keeps UX consistent while making the workflow configurable.

    default_anchors: List[str] = []
    prof_anchors = prof.get("uart_anchors_default")
    if isinstance(prof_anchors, list):
        default_anchors = [str(x) for x in prof_anchors]

    for f in fields:
        if f == "symptom":
            _case_set(data, "symptom", _prompt_safe("symptom", default=str(data.get("symptom") or "")))
        elif f == "impact_scope":
            _case_set(data, "impact_scope", _prompt_safe("impact_scope", default=str(data.get("impact_scope") or "")))
        elif f == "firmware_version":
            _case_set(
                data,
                "firmware_version",
                _prompt_safe("firmware_version", default=str(data.get("firmware_version") or "")),
            )
        elif f == "hw_revision":
            _case_set(data, "hw_revision", _prompt_safe("hw_revision", default=str(data.get("hw_revision") or "")))
        elif f == "time_window":
            _case_set(data, "time_window", _prompt_safe("time_window", default=str(data.get("time_window") or "")))
        elif f == "repro_steps":
            if no_editor:
                v = _prompt_safe("repro_steps", default=str(data.get("repro_steps") or ""))
                _case_set(data, "repro_steps", (str(v).rstrip() + "\n") if v else "\n")
            else:
                typer.echo("Enter repro_steps (opens editor).")
                current = str(data.get("repro_steps") or "")
                edited = typer.edit(current) or current
                _case_set(data, "repro_steps", (edited.rstrip() + "\n") if edited else "\n")

        elif f == "uart_log_format":
            _case_set(
                data,
                "uart_log_format",
                _prompt_safe("uart_log_format", default=str(data.get("uart_log_format") or "mixed")).strip(),
            )
        elif f == "can_enable_more_logs":
            v = typer.confirm(
                "Can you enable more detailed UART logs (power/bt/charger)?",
                default=bool(data.get("can_enable_more_logs") or False),
            )
            _case_set(data, "can_enable_more_logs", bool(v))
            if v:
                if no_editor:
                    how = _prompt_safe("enable_more_logs_how", default=str(data.get("enable_more_logs_how") or ""))
                    _case_set(data, "enable_more_logs_how", (str(how).rstrip() + "\n") if how else "")
                else:
                    typer.echo("Enter enable_more_logs_how (opens editor).")
                    cur = str(data.get("enable_more_logs_how") or "")
                    how = typer.edit(cur) or cur
                    _case_set(data, "enable_more_logs_how", (how.rstrip() + "\n") if how else "")
        elif f == "capabilities_phone_side":
            _case_set(
                data,
                "capabilities_phone_side",
                _prompt_safe(
                    "phone_side (android/ios/none/unknown)",
                    default=str(data.get("capabilities_phone_side") or "unknown"),
                ).strip(),
            )
        elif f == "capabilities_power_measure":
            _case_set(
                data,
                "capabilities_power_measure",
                _prompt_safe(
                    "power_measure (none/multimeter/analyzer/onboard/unknown)",
                    default=str(data.get("capabilities_power_measure") or "unknown"),
                ).strip(),
            )
        elif f == "capabilities_bt_snoop":
            _case_set(
                data,
                "capabilities_bt_snoop",
                _prompt_safe(
                    "bt_snoop (yes/no/unknown)",
                    default=str(data.get("capabilities_bt_snoop") or "unknown"),
                ).strip(),
            )
        elif f == "capabilities_pmic_dump":
            _case_set(
                data,
                "capabilities_pmic_dump",
                _prompt_safe(
                    "pmic_dump (yes/no/unknown)",
                    default=str(data.get("capabilities_pmic_dump") or "unknown"),
                ).strip(),
            )
        elif f == "anchor_keywords":
            anchor_current = data.get("anchor_keywords")
            anchors: List[str]
            if isinstance(anchor_current, list):
                anchors = [str(x) for x in anchor_current]
            else:
                anchors = []
            if not anchors and default_anchors:
                anchors = default_anchors[:8]
            typer.echo("Enter anchor keywords (one per line; blank line to finish).")
            if anchors:
                typer.echo(f"Current anchors: {anchors}")
            new_anchors: List[str] = []
            while True:
                s = typer.prompt("anchor", default="", show_default=False).strip()
                if not s:
                    break
                new_anchors.append(s)
            if new_anchors:
                anchors = new_anchors
            _case_set(data, "anchor_keywords", anchors)

        else:
            # Unknown field: store a simple string prompt to keep profile extensible.
            _case_set(data, f, _prompt_safe(f, default=str(data.get(f) or "")))

    data["updated_at"] = _now_iso()
    if "created_at" not in data:
        data["created_at"] = _now_iso()
    _dump_yaml(case_path, data)
    typer.echo(f"Wrote {case_path}")


evidence_app = typer.Typer(add_completion=False)
app.add_typer(evidence_app, name="evidence", help="Manage evidence (EIDs)")


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
    if etype_norm not in {"log", "code", "cmd"}:
        raise typer.BadParameter("--type must be one of: log, code, cmd")

    root = _repo_root()
    tdir = _triage_dir(root)
    if not tdir.exists():
        raise typer.BadParameter("triage/ does not exist. Run: triage init")

    eid = _next_eid(tdir)

    snippet = ""
    if content_file is not None:
        snippet = content_file.read_text(encoding="utf-8")
    elif content is not None:
        snippet = content
    else:
        snippet = typer.edit("") or ""

    folder = tdir / "evidence" / etype_norm
    fname = f"{eid}_{etype_norm}.txt"
    out_path = folder / fname
    header = (
        f"EID: {eid}\n"
        f"Type: {etype_norm}\n"
        f"Source: {source}\n"
        f"Captured: {_now_iso()}\n"
        f"Note: {note}\n"
        "---\n"
    )
    _write_text(out_path, header + snippet.rstrip() + "\n")

    _append_evidence_index(tdir, eid=eid, etype=etype_norm, source=source, note=note)
    typer.echo(f"Added {eid}: {out_path}")


@evidence_app.command("add-log")
def evidence_add_log(
    log_path: Path = typer.Option(..., exists=True, dir_okay=False, help="Log file path"),
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

    if line_start is not None or line_end is not None:
        if line_start is None or line_end is None:
            raise typer.BadParameter("--line-start and --line-end must be provided together")
        if line_end < line_start:
            raise typer.BadParameter("--line-end must be >= --line-start")

        # Capture a fixed range as a single evidence.
        start = int(line_start)
        end = int(line_end)
        out_lines: List[str] = []
        with log_path.open("r", encoding="utf-8", errors="replace") as f:
            for i, raw in enumerate(f, start=1):
                if i < start:
                    continue
                if i > end:
                    break
                out_lines.append(f"{i}: {raw.rstrip()}")

        if not out_lines:
            raise typer.BadParameter("Selected line range is empty")

        eid = _next_eid(tdir)
        source = f"{log_path}:{start}-{end}"
        out_path = tdir / "evidence" / "log" / f"{eid}_log.txt"
        header = (
            f"EID: {eid}\n"
            "Type: log\n"
            f"Source: {source}\n"
            f"Captured: {_now_iso()}\n"
            f"Note: {note}\n"
            "---\n"
        )
        _write_text(out_path, header + "\n".join(out_lines).rstrip() + "\n")
        _append_evidence_index(tdir, eid=eid, etype="log", source=source, note=note)
        typer.echo(f"Added {eid}: {out_path}")
        return

    pattern = [p for p in pattern if p.strip()]
    if not pattern:
        raise typer.BadParameter("At least one --pattern is required")
    combined = "|".join([f"(?:{p})" for p in pattern])
    try:
        rx = re.compile(combined)
    except re.error as e:
        raise typer.BadParameter(f"Invalid regex pattern: {e}")

    from collections import deque

    buf_before: deque[tuple[int, str]] = deque(maxlen=before)
    captures = 0
    line_no = 0

    def _write_capture(match_line_no: int, before_lines: list[tuple[int, str]], match_line: str, after_lines: list[tuple[int, str]]) -> None:
        nonlocal captures
        eid = _next_eid(tdir)
        start = before_lines[0][0] if before_lines else match_line_no
        end = after_lines[-1][0] if after_lines else match_line_no
        source = f"{log_path}:{start}-{end}"
        out_path = tdir / "evidence" / "log" / f"{eid}_log.txt"
        header = (
            f"EID: {eid}\n"
            "Type: log\n"
            f"Source: {source}\n"
            f"Captured: {_now_iso()}\n"
            f"Note: {note}\n"
            "Match: /" + combined + f"/ at line {match_line_no}\n"
            "---\n"
        )
        body_lines: List[str] = []
        for ln, s in before_lines:
            body_lines.append(f"{ln}: {s}")
        body_lines.append(f"{match_line_no}: {match_line}")
        for ln, s in after_lines:
            body_lines.append(f"{ln}: {s}")
        _write_text(out_path, header + "\n".join(body_lines).rstrip() + "\n")
        _append_evidence_index(tdir, eid=eid, etype="log", source=source, note=note)
        captures += 1
        typer.echo(f"Added {eid}: {out_path}")

    with log_path.open("r", encoding="utf-8", errors="replace") as f:
        it = iter(f)
        for raw in it:
            line_no += 1
            line = raw.rstrip("\n")
            if rx.search(line):
                before_lines = list(buf_before)
                after_lines: list[tuple[int, str]] = []
                for i in range(after):
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

    if captures == 0:
        raise typer.Exit(code=1)


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

    index_text = _read_text_if_exists(tdir / "evidence" / "index.md")
    known_eids = set(re.findall(r"\bE\d{3}\b", index_text))
    disk_eids = set(_evidence_files_on_disk(tdir).keys())

    errors: List[str] = []

    # Facts: ban speculation words
    facts_path = tdir / "facts.md"
    facts_text = _read_text_if_exists(facts_path)
    banned = [
        # keep this list short; add more when needed
        "possible",
        "probably",
        "should",
        "might",
        "可能",
        "怀疑",
        "大概",
        "应该",
        "推测",
        "估计",
        "也许",
    ]
    for w in banned:
        if w in facts_text:
            errors.append(f"facts.md contains banned speculation word: {w}")
            break

    # Facts: each non-empty F### line must cite an EID
    for line in facts_text.splitlines():
        m = re.match(r"^(F\d{3}):\s*(.*)$", line)
        if not m:
            continue
        payload = m.group(2).strip()
        if not payload:
            continue
        if not re.search(r"\bE\d{3}\b", payload):
            errors.append(f"facts.md fact '{m.group(1)}' cites no EID")
            break

    # Hypotheses and directions: each heading block must cite at least one known EID
    def _check_blocks(path: Path, label: str, header_re: str) -> None:
        text = _read_text_if_exists(path)
        if not text.strip():
            return
        # Split by headings that start at line start.
        lines = text.splitlines()
        cur_header = None
        cur_buf: List[str] = []
        blocks: list[tuple[str, str]] = []
        hpat = re.compile(header_re)
        for line in lines:
            m = hpat.match(line)
            if m:
                if cur_header is not None:
                    blocks.append((cur_header, "\n".join(cur_buf)))
                cur_header = m.group(0)
                cur_buf = [line]
            else:
                if cur_header is not None:
                    cur_buf.append(line)
        if cur_header is not None:
            blocks.append((cur_header, "\n".join(cur_buf)))

        for header, body in blocks:
            eids = set(re.findall(r"\bE\d{3}\b", body))
            if not eids:
                errors.append(f"{label}: block '{header}' cites no EID")
                continue
            unknown = sorted(eids - known_eids)
            if unknown:
                errors.append(f"{label}: block '{header}' cites unknown EIDs: {', '.join(unknown)}")
            missing_files = sorted(eids - disk_eids)
            if missing_files:
                errors.append(f"{label}: block '{header}' references EIDs missing evidence files: {', '.join(missing_files)}")

    _check_blocks(tdir / "hypotheses.md", "hypotheses.md", r"^H\d{3}\b.*")
    _check_blocks(tdir / "directions.md", "directions.md", r"^DIR-\d+\b.*")

    if errors:
        for e in errors:
            typer.echo(f"ERROR: {e}")
        raise typer.Exit(code=2)

    typer.echo("OK: validation passed")


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

    eids = [e.strip().upper() for e in evidence if e.strip()]
    if not eids:
        raise typer.BadParameter("At least one --evidence E### is required")
    for e in eids:
        if not re.fullmatch(r"E\d{3}", e):
            raise typer.BadParameter(f"Invalid evidence id: {e}")
    _assert_eids_exist(tdir, eids)

    facts_path = tdir / "facts.md"
    fid = _next_id(facts_path, "F")
    line = f"{fid}: {text.strip()} ({', '.join(sorted(set(eids)))})"
    _append_block(facts_path, line)
    typer.echo(f"Added {fid} to {facts_path}")


@facts_app.command("list")
def facts_list() -> None:
    root = _repo_root()
    tdir = _triage_dir(root)
    facts_path = tdir / "facts.md"
    text = _read_text_if_exists(facts_path)
    for line in text.splitlines():
        m = re.match(r"^(F\d{3}):\s*(.*)$", line)
        if not m:
            continue
        typer.echo(f"{m.group(1)}: {m.group(2)}")


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

    fid = fid.strip().upper()
    if not re.fullmatch(r"F\d{3}", fid):
        raise typer.BadParameter("--id must be like F001")

    eids = [e.strip().upper() for e in evidence if e.strip()]
    if not eids:
        raise typer.BadParameter("At least one --evidence E### is required")
    for e in eids:
        if not re.fullmatch(r"E\d{3}", e):
            raise typer.BadParameter(f"Invalid evidence id: {e}")
    _assert_eids_exist(tdir, eids)

    facts_path = tdir / "facts.md"
    lines = _read_text_if_exists(facts_path).splitlines()
    updated = False
    out: List[str] = []
    replacement = f"{fid}: {text.strip()} ({', '.join(sorted(set(eids)))})"
    for line in lines:
        if re.match(rf"^{re.escape(fid)}:\b", line):
            out.append(replacement)
            updated = True
        else:
            out.append(line)
    if not updated:
        raise typer.BadParameter(f"Fact id not found: {fid}")
    _write_text(facts_path, "\n".join(out).rstrip() + "\n")
    typer.echo(f"Updated {fid} in {facts_path}")


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

    eids = [e.strip().upper() for e in evidence if e.strip()]
    if not eids:
        raise typer.BadParameter("At least one --evidence E### is required")
    for e in eids:
        if not re.fullmatch(r"E\d{3}", e):
            raise typer.BadParameter(f"Invalid evidence id: {e}")
    _assert_eids_exist(tdir, eids)

    hyp_path = tdir / "hypotheses.md"
    hid = _next_id(hyp_path, "H")
    block = (
        f"{hid} (Status: {status.strip()} | Confidence: {confidence.strip()})\n"
        f"Hypothesis: {hypothesis.strip()}\n"
        f"Evidence: ({', '.join(sorted(set(eids)))})\n"
        + (f"Test: {test.strip()}\n" if test.strip() else "Test: \n")
    )
    _append_block(hyp_path, block)
    typer.echo(f"Added {hid} to {hyp_path}")


@hyp_app.command("list")
def hypotheses_list() -> None:
    root = _repo_root()
    tdir = _triage_dir(root)
    hyp_path = tdir / "hypotheses.md"
    text = _read_text_if_exists(hyp_path)
    blocks = _split_blocks(text, r"^H\d{3}\b.*")
    for b in blocks:
        header = b[0]
        hid_m = re.match(r"^(H\d{3})\b", header)
        if not hid_m:
            continue
        hid = hid_m.group(1)
        status_m = re.search(r"Status:\s*([^|)]+)", header)
        conf_m = re.search(r"Confidence:\s*([^|)]+)", header)
        status = status_m.group(1).strip() if status_m else "?"
        conf = conf_m.group(1).strip() if conf_m else "?"
        eids = sorted(set(re.findall(r"\bE\d{3}\b", "\n".join(b))))
        typer.echo(f"{hid} [{status}/{conf}] EIDs: {', '.join(eids) if eids else 'none'}")


@hyp_app.command("close")
def hypotheses_close(
    hid: str = typer.Option(..., "--id", help="Hypothesis id (H###)"),
    reason: str = typer.Option("", help="Why closed (fact only)"),
) -> None:
    root = _repo_root()
    tdir = _triage_dir(root)
    hyp_path = tdir / "hypotheses.md"
    text = _read_text_if_exists(hyp_path)
    blocks = _split_blocks(text, r"^H\d{3}\b.*")
    hid = hid.strip().upper()
    if not re.fullmatch(r"H\d{3}", hid):
        raise typer.BadParameter("--id must be like H001")
    found = False
    out_blocks: List[List[str]] = []
    for b in blocks:
        if not b:
            continue
        header = b[0]
        if header.startswith(hid + " ") or header == hid or header.startswith(hid + "("):
            # Replace Status: ... with Status: Closed
            new_header = re.sub(r"Status:\s*[^|)]+", "Status: Closed", header)
            if new_header == header and "Status:" not in header:
                new_header = header + " | Status: Closed"
            b2 = [new_header] + b[1:]
            if reason.strip():
                b2.append(f"Closed because: {reason.strip()}")
            out_blocks.append(b2)
            found = True
        else:
            out_blocks.append(b)
    if not found:
        raise typer.BadParameter(f"Hypothesis id not found: {hid}")
    _write_text(hyp_path, _join_blocks(out_blocks))
    typer.echo(f"Closed {hid} in {hyp_path}")


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

    eids = [e.strip().upper() for e in evidence if e.strip()]
    if not eids:
        raise typer.BadParameter("At least one --evidence E### is required")
    for e in eids:
        if not re.fullmatch(r"E\d{3}", e):
            raise typer.BadParameter(f"Invalid evidence id: {e}")
    _assert_eids_exist(tdir, eids)

    directions_path = tdir / "directions.md"
    # DIR-1, DIR-2 ...
    text = _read_text_if_exists(directions_path)
    nums: list[int] = []
    for m in re.finditer(r"\bDIR-(\d+)\b", text):
        nums.append(int(m.group(1)))
    n = (max(nums) + 1) if nums else 1
    did = f"DIR-{n}"

    block = (
        f"{did} (Confidence: {confidence.strip()})\n"
        f"Direction: {direction.strip()}\n"
        f"Evidence chain: ({', '.join(sorted(set(eids)))})\n"
        + (f"Next minimal test: {next_test.strip()}\n" if next_test.strip() else "Next minimal test: \n")
        + (f"Falsify if: {falsify_if.strip()}\n" if falsify_if.strip() else "Falsify if: \n")
    )
    _append_block(directions_path, block)
    typer.echo(f"Added {did} to {directions_path}")


@dir_app.command("list")
def directions_list() -> None:
    root = _repo_root()
    tdir = _triage_dir(root)
    directions_path = tdir / "directions.md"
    text = _read_text_if_exists(directions_path)
    blocks = _split_blocks(text, r"^DIR-\d+\b.*")
    for b in blocks:
        header = b[0]
        mid = re.match(r"^(DIR-\d+)\b", header)
        if not mid:
            continue
        did = mid.group(1)
        conf_m = re.search(r"Confidence:\s*([^|)]+)", header)
        conf = conf_m.group(1).strip() if conf_m else "?"
        eids = sorted(set(re.findall(r"\bE\d{3}\b", "\n".join(b))))
        typer.echo(f"{did} [{conf}] EIDs: {', '.join(eids) if eids else 'none'}")


@dir_app.command("prune")
def directions_prune(
    top_n: int = typer.Option(3, min=1, max=10, help="Keep only first N direction blocks"),
) -> None:
    root = _repo_root()
    tdir = _triage_dir(root)
    directions_path = tdir / "directions.md"
    text = _read_text_if_exists(directions_path)
    blocks = _split_blocks(text, r"^DIR-\d+\b.*")
    if not blocks:
        raise typer.BadParameter("No direction blocks found")
    kept = blocks[:top_n]
    _write_text(directions_path, _join_blocks(kept))
    typer.echo(f"Pruned directions to top {top_n} in {directions_path}")


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

    case = _load_yaml(tdir / "case.yaml")
    title = case.get("title") or ""
    case_id = case.get("case_id") or ""

    index_text = _read_text_if_exists(tdir / "evidence" / "index.md")
    eids = re.findall(r"\bE\d{3}\b", index_text)
    last_eids = list(dict.fromkeys(eids))[-5:]

    def _first_lines(path: Path, n: int) -> str:
        lines = _read_text_if_exists(path).splitlines()
        return "\n".join(lines[:n]).strip()

    typer.echo(f"Case: {case_id} {title}")
    typer.echo(f"Triage dir: {tdir}")
    typer.echo(f"Evidence count: {len(set(eids))} (latest: {', '.join(last_eids) if last_eids else 'none'})")
    typer.echo("")
    typer.echo("Facts (top):")
    typer.echo(_first_lines(tdir / "facts.md", 12) or "(empty)")
    typer.echo("")
    typer.echo("Hypotheses (top):")
    typer.echo(_first_lines(tdir / "hypotheses.md", 18) or "(empty)")
    typer.echo("")
    typer.echo("Directions (top):")
    typer.echo(_first_lines(tdir / "directions.md", 18) or "(empty)")


@app.command("direction-build")
def direction_build(
    top_n: int = typer.Option(3, min=1, max=5, help="Number of directions to keep"),
    overwrite: bool = typer.Option(False, help="Overwrite directions.md if it exists"),
) -> None:
    """Build Top directions from evidence-backed hypotheses (MVP scoring)."""

    root = _repo_root()
    tdir = _triage_dir(root)
    if not tdir.exists():
        raise typer.BadParameter("triage/ does not exist. Run: triage init")

    directions_path = tdir / "directions.md"
    existing = _read_text_if_exists(directions_path).strip()
    if existing and not overwrite:
        raise typer.BadParameter(f"{directions_path} exists. Re-run with --overwrite")

    ev_index = _parse_evidence_index(tdir)
    known = _known_eids(tdir)
    disk = set(_evidence_files_on_disk(tdir).keys())

    # Parse hypotheses blocks (very tolerant, markdown-ish).
    hyp_text = _read_text_if_exists(tdir / "hypotheses.md")
    if not re.search(r"^H\d{3}\b", hyp_text, flags=re.MULTILINE):
        raise typer.BadParameter("No hypotheses found. Add evidence-backed hypotheses first.")
    lines = hyp_text.splitlines()
    blocks: list[dict[str, object]] = []
    cur_id: Optional[str] = None
    cur_lines: List[str] = []
    for line in lines:
        m = re.match(r"^(H\d{3})\b(.*)$", line)
        if m:
            if cur_id is not None:
                blocks.append({"id": cur_id, "text": "\n".join(cur_lines)})
            cur_id = m.group(1)
            cur_lines = [line]
        else:
            if cur_id is not None:
                cur_lines.append(line)
    if cur_id is not None:
        blocks.append({"id": cur_id, "text": "\n".join(cur_lines)})

    scored: list[tuple[int, dict[str, object]]] = []
    for b in blocks:
        text = str(b["text"])
        eids: List[str] = sorted(set(re.findall(r"\bE\d{3}\b", text)))
        if not eids:
            continue
        # Evidence-backed: at least one cited EID must exist in index and have a file on disk.
        if not any((e in known and e in disk) for e in eids):
            continue
        log_eids = [e for e in eids if ev_index.get(e, {}).get("type") == "log"]
        status_open = bool(re.search(r"Status:\s*Open\b", text, flags=re.IGNORECASE))
        score = 0
        score += len(eids)
        score += 2 * len(log_eids)
        if status_open:
            score += 2
        scored.append((score, {"id": b["id"], "eids": eids, "text": text, "score": score}))

    # Deterministic ordering: score desc, then hypothesis id asc.
    scored.sort(key=lambda t: (-t[0], str(t[1].get("id") or "")))
    top = [b for _, b in scored[:top_n]]

    if not top:
        raise typer.BadParameter("No evidence-backed hypotheses found. Add evidence first, then cite real EIDs in hypotheses.md.")

    out_lines: List[str] = []
    out_lines.append("# Directions")
    out_lines.append("")
    out_lines.append("Generated from evidence-backed hypotheses.")
    out_lines.append("Rules: keep top 1-3 directions; each must cite EIDs.")
    out_lines.append("")

    for i, b in enumerate(top, start=1):
        eids = list(b["eids"])  # type: ignore[assignment]
        hid = str(b["id"])
        out_lines.append(f"DIR-{i} (From: {hid} | Confidence: Medium)")
        out_lines.append("Direction: <fill: component / chain / data / dependency / config>")
        out_lines.append("Evidence chain: (" + ", ".join(eids[:5]) + (", ..." if len(eids) > 5 else "") + ")")
        out_lines.append("Next minimal test: <one discriminative test to separate top directions>")
        out_lines.append("Falsify if: <what observation would kill this direction>")
        out_lines.append("")

    _write_text(directions_path, "\n".join(out_lines).rstrip() + "\n")
    typer.echo(f"Wrote {directions_path} ({len(top)} directions)")


@app.command("next")
def next_steps() -> None:
    """Print the recommended golden-path next command based on workspace state."""

    root = _repo_root()
    tdir = _triage_dir(root)
    if not tdir.exists():
        typer.echo("Next: init")
        raise typer.Exit(code=0)

    prof_path = tdir / "profile.yaml"
    case_path = tdir / "case.yaml"
    if not prof_path.exists():
        typer.echo("Next: init --profile <profile_id>")
        raise typer.Exit(code=0)
    if not case_path.exists():
        typer.echo("Next: round run 0")
        raise typer.Exit(code=0)

    case = _load_yaml(case_path)
    profile = _load_active_profile(tdir)

    required0 = _get_profile_round_fields(profile, 0)
    if required0 and any(_is_missing_case_field(case, k) for k in required0):
        typer.echo("Next: round run 0")
        raise typer.Exit(code=0)

    required1 = _get_profile_round_fields(profile, 1)
    if required1 and any(_is_missing_case_field(case, k) for k in required1):
        typer.echo("Next: round run 1")
        raise typer.Exit(code=0)

    # If no evidence yet
    index_path = tdir / "evidence" / "index.md"
    if not index_path.exists() or not re.search(r"\bE\d{3}\b", _read_text_if_exists(index_path)):
        required_ev = _profile_required_evidence(profile)
        if "uart_log" in required_ev:
            anchors = case.get("anchor_keywords")
            if isinstance(anchors, list) and anchors:
                hint = anchors[0]
            else:
                hint = "panic"
            typer.echo(f"Next: evidence add-log --log-path <uart.log> --pattern {hint}")
        else:
            typer.echo("Next: evidence add --type cmd --source <source> --note <fact> --content <text>")
        raise typer.Exit(code=0)

    facts_path = tdir / "facts.md"
    facts_text = _read_text_if_exists(facts_path)
    facts_exist = bool(re.search(r"^F\d{3}:\s*.+\bE\d{3}\b", facts_text, flags=re.MULTILINE))
    if not facts_exist:
        eid = _latest_eid(tdir) or "E001"
        typer.echo(f"Next: facts add --text <fact> --evidence {eid}")
        raise typer.Exit(code=0)

    hyp_path = tdir / "hypotheses.md"
    hyp_text = _read_text_if_exists(hyp_path)
    if not _has_real_hypothesis(tdir):
        eid = _latest_eid(tdir) or "E001"
        typer.echo(f"Next: hypotheses add --hypothesis <...> --evidence {eid}")
        raise typer.Exit(code=0)

    if not _has_generated_directions(tdir):
        typer.echo("Next: direction-build --overwrite")
        raise typer.Exit(code=0)

    typer.echo("Next: validate")


def main() -> None:
    app()


acceptance_app = typer.Typer(add_completion=False)
app.add_typer(acceptance_app, name="acceptance", help="Acceptance checks (developer workflow)")


@acceptance_app.command("run")
def acceptance_run() -> None:
    """Run acceptance suite from YAML cases (workflow-driven development)."""

    from typer.testing import CliRunner

    runner = CliRunner()

    cases_dir = Path(__file__).resolve().parent / "acceptance" / "cases"
    case_files = sorted(cases_dir.glob("*.yaml"))
    if not case_files:
        typer.echo(f"No acceptance cases found in {cases_dir}")
        raise typer.Exit(code=2)

    def _sub_vars(s: str, vars_map: dict) -> str:
        out = s
        for k, v in vars_map.items():
            out = out.replace("${" + k + "}", str(v))
        return out

    def _invoke(root: Path, argv: List[str], *, input_text: Optional[str] = None) -> int:
        res = runner.invoke(app, ["--root", str(root)] + argv, input=input_text)
        return res.exit_code

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
                    last_stdout = res_run.stdout
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


if __name__ == "__main__":
    main()

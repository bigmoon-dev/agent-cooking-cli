from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import List, Optional

import click
import typer

from .core import dump_yaml, load_yaml, now_iso
from .profile import get_round_fields, load_active_profile


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
        raise typer.BadParameter(
            "Input exhausted (non-interactive stdin). Provide --no-editor input or run interactively."
        )


def run_round(tdir: Path, *, round_id: int, no_editor: bool) -> None:
    """Run a profile-driven round (field order controlled by profile)."""

    prof = load_active_profile(triage_dir=tdir, load_yaml_func=load_yaml)
    fields = get_round_fields(prof, round_id)
    if not fields:
        raise typer.BadParameter(f"No fields found for round {round_id}. Check triage/profile.yaml")

    case_path = tdir / "case.yaml"
    data = load_yaml(case_path)

    default_anchors: List[str] = []
    prof_anchors = prof.get("uart_anchors_default")
    if isinstance(prof_anchors, list):
        default_anchors = [str(x) for x in prof_anchors]

    for f in fields:
        if f == "symptom":
            _case_set(data, "symptom", _prompt_safe("symptom", default=str(data.get("symptom") or "")))
        elif f == "impact_scope":
            _case_set(
                data,
                "impact_scope",
                _prompt_safe("impact_scope", default=str(data.get("impact_scope") or "")),
            )
        elif f == "firmware_version":
            _case_set(
                data,
                "firmware_version",
                _prompt_safe("firmware_version", default=str(data.get("firmware_version") or "")),
            )
        elif f == "hw_revision":
            _case_set(
                data,
                "hw_revision",
                _prompt_safe("hw_revision", default=str(data.get("hw_revision") or "")),
            )
        elif f == "time_window":
            _case_set(
                data,
                "time_window",
                _prompt_safe("time_window", default=str(data.get("time_window") or "")),
            )
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

        elif f == "enable_more_logs_how":
            cur = str(data.get("enable_more_logs_how") or "")
            if no_editor:
                v = _prompt_safe("enable_more_logs_how", default=cur)
                _case_set(data, "enable_more_logs_how", (v.rstrip() + "\n") if v else "")
            else:
                typer.echo("Enter enable_more_logs_how (opens editor).")
                edited = typer.edit(cur) or cur
                _case_set(data, "enable_more_logs_how", (edited.rstrip() + "\n") if edited else "")

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
            typer.echo("These are used to locate high-signal windows in UART logs.")
            if anchors:
                typer.echo(f"Current anchors: {anchors}")
            new_anchors: List[str] = []
            while True:
                try:
                    s = typer.prompt("anchor", default="", show_default=False)
                except (EOFError, click.Abort):
                    # Treat exhausted stdin as "finish anchors".
                    break
                s = str(s).strip()
                if not s:
                    break
                new_anchors.append(s)
            if new_anchors:
                anchors = new_anchors
            _case_set(data, "anchor_keywords", anchors)

        else:
            _case_set(data, f, _prompt_safe(f, default=str(data.get(f) or "")))

    data["updated_at"] = now_iso()
    if "created_at" not in data:
        data["created_at"] = now_iso()
    dump_yaml(case_path, data)
    typer.echo(f"Wrote {case_path}")


def deprecated_round0(
    tdir: Path,
    *,
    case_id: Optional[str],
    title: Optional[str],
    description: Optional[str],
    edit: bool,
) -> None:
    """Round 0: collect inputs into triage/case.yaml."""

    case_path = tdir / "case.yaml"
    data = load_yaml(case_path)

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
            description = typer.prompt(
                "problem_description", default=str(data.get("problem_description") or "")
            )
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
            "updated_at": now_iso(),
        }
    )
    if "created_at" not in data:
        data["created_at"] = now_iso()

    dump_yaml(case_path, data)
    typer.echo(f"Wrote {case_path}")
    typer.echo("NOTE: 'round 0' is deprecated. Use: round run 0")


def deprecated_round1(tdir: Path) -> None:
    """Round 1: capture capabilities + UART anchors (profile-driven if present)."""

    case_path = tdir / "case.yaml"
    data = load_yaml(case_path)
    prof = load_active_profile(triage_dir=tdir, load_yaml_func=load_yaml)
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
            "updated_at": now_iso(),
        }
    )
    if "created_at" not in data:
        data["created_at"] = now_iso()
    dump_yaml(case_path, data)
    typer.echo(f"Wrote {case_path}")
    typer.echo("NOTE: 'round 1' is deprecated. Use: round run 1")

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, List, Optional

import typer
import yaml


def profiles_dir() -> Path:
    return Path(__file__).resolve().parent / "profiles"


# ---------------------------------------------------------------------------
# Extensible profile loader: allows enterprise/plugin code to register an
# alternative loader via set_profile_loader() instead of monkey-patching.
# ---------------------------------------------------------------------------
_custom_profile_loader: Optional[Callable[[str], dict]] = None


def set_profile_loader(loader: Optional[Callable[[str], dict]]) -> None:
    """Register a custom profile loader.

    When set, ``load_profile_yaml`` delegates to *loader* first.
    If *loader* raises ``FileNotFoundError``, the built-in loader is
    used as fallback.  Pass ``None`` to restore default behaviour.
    """
    global _custom_profile_loader
    _custom_profile_loader = loader


def get_profile_loader() -> Optional[Callable[[str], dict]]:
    """Return the currently registered custom profile loader, or ``None``."""
    return _custom_profile_loader


def _builtin_load_profile_yaml(profile_id: str) -> dict:
    """Built-in profile loader: reads from the bundled profiles/ directory."""
    pid = profile_id.strip()
    if not pid:
        raise typer.BadParameter("profile_id is required")
    p = profiles_dir() / f"{pid}.yaml"
    if not p.exists():
        raise typer.BadParameter(f"Unknown profile_id '{pid}'. Expected file: {p}")
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise typer.BadParameter(f"Invalid profile YAML: {p}")
    return data


def load_profile_yaml(profile_id: str) -> dict:
    """Load a profile by ID — delegates to custom loader if registered."""
    pid = profile_id.strip()
    if not pid:
        raise typer.BadParameter("profile_id is required")
    if _custom_profile_loader is not None:
        try:
            return _custom_profile_loader(pid)
        except FileNotFoundError:
            pass  # fallback to built-in
    return _builtin_load_profile_yaml(profile_id)


def validate_profile(profile: dict) -> List[str]:
    errors: List[str] = []
    if not isinstance(profile, dict):
        return ["profile must be a YAML mapping"]

    pid = profile.get("profile_id")
    if not isinstance(pid, str) or not pid.strip():
        errors.append("profile_id: required non-empty string")

    rounds = profile.get("rounds")
    if not isinstance(rounds, list) or not rounds:
        errors.append("rounds: required non-empty list")
        return errors

    seen_round_ids: set[int] = set()
    for i, r in enumerate(rounds):
        if not isinstance(r, dict):
            errors.append(f"rounds[{i}]: must be a mapping")
            continue
        rid = r.get("id")
        if not isinstance(rid, int):
            errors.append(f"rounds[{i}].id: required int")
            continue
        if rid < 0:
            errors.append(f"rounds[{i}].id: must be >= 0")
        if rid in seen_round_ids:
            errors.append(f"rounds[{i}].id: duplicate id {rid}")
        seen_round_ids.add(rid)

        fields = r.get("fields")
        if not isinstance(fields, list) or not fields:
            errors.append(f"rounds[{i}].fields: required non-empty list")
            continue
        for j, f in enumerate(fields):
            if not isinstance(f, str) or not f.strip():
                errors.append(f"rounds[{i}].fields[{j}]: must be non-empty string")

    req_ev = profile.get("required_evidence")
    if req_ev is not None and not isinstance(req_ev, list):
        errors.append("required_evidence: must be a list if present")
    if isinstance(req_ev, list):
        for j, e in enumerate(req_ev):
            if not isinstance(e, str) or not e.strip():
                errors.append(f"required_evidence[{j}]: must be non-empty string")

    tax = profile.get("direction_taxonomy")
    if tax is not None and not isinstance(tax, list):
        errors.append("direction_taxonomy: must be a list if present")
    if isinstance(tax, list):
        for j, t in enumerate(tax):
            if not isinstance(t, str) or not t.strip():
                errors.append(f"direction_taxonomy[{j}]: must be non-empty string")

    return errors


def require_valid_profile(profile: dict) -> dict:
    errs = validate_profile(profile)
    if errs:
        msg = "Invalid profile:\n" + "\n".join(["- " + e for e in errs])
        raise typer.BadParameter(msg)
    return profile


def get_round_fields(profile: dict, round_id: int) -> List[str]:
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


def profile_required_evidence(profile: dict) -> List[str]:
    v = profile.get("required_evidence")
    if isinstance(v, list):
        return [str(x) for x in v]
    return []


def load_active_profile(*, triage_dir: Path, load_yaml_func: Callable[[Path], dict]) -> dict:
    """Load triage/profile.yaml if present; else return empty."""

    p = triage_dir / "profile.yaml"
    if not p.exists():
        return {}
    return require_valid_profile(load_yaml_func(p))


def looks_like_profile_id(s: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_\-]+", s))


def profile_validate_command(
    load_yaml_func,
    repo_root_func,
    triage_dir_func,
    profile_id: Optional[str],
    path: Optional[Path],
) -> None:
    if profile_id is None and path is None:
        root = repo_root_func()
        tdir = triage_dir_func(root)
        path = tdir / "profile.yaml"
        if not path.exists():
            raise typer.BadParameter("No profile specified and triage/profile.yaml not found")

    if profile_id is not None and path is not None:
        raise typer.BadParameter("Specify either profile_id or --path, not both")

    if profile_id is not None:
        prof = load_profile_yaml(profile_id)
    else:
        assert path is not None  # nosec B101
        prof = load_yaml_func(path)

    errs = validate_profile(prof)
    if errs:
        for e in errs:
            typer.echo(f"ERROR: {e}")
        raise typer.Exit(code=2)
    typer.echo("OK: profile valid")

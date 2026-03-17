from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import typer
import yaml

from .profile import load_profile_yaml, profile_validate_command, profiles_dir


def list_profiles() -> None:
    """List built-in profiles."""

    d = profiles_dir()
    if not d.exists():
        typer.echo("No profiles directory")
        raise typer.Exit(code=1)
    profs = sorted([p.stem for p in d.glob("*.yaml")])
    for p in profs:
        typer.echo(p)


def show_profile(profile_id: str) -> None:
    """Show a built-in profile YAML."""

    prof = load_profile_yaml(profile_id)
    typer.echo(yaml.safe_dump(prof, sort_keys=False, allow_unicode=False))


def validate_profile(
    *,
    load_yaml_func: Callable[[Path], dict],
    repo_root_func: Callable[[], Path],
    triage_dir_func: Callable[[Path], Path],
    profile_id: Optional[str],
    path: Optional[Path],
) -> None:
    """Validate a profile (built-in or a profile.yaml file)."""

    profile_validate_command(load_yaml_func, repo_root_func, triage_dir_func, profile_id, path)

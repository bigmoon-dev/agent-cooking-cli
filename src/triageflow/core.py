from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Optional

import typer
import yaml

TRIAGE_DIRNAME = "triage"


class Workspace:
    def __init__(self) -> None:
        self.root: Optional[Path] = None

    def set_root(self, root: Optional[Path]) -> None:
        self.root = root

    def repo_root(self) -> Path:
        if self.root is not None:
            return self.root
        return Path.cwd()

    def triage_dir(self) -> Path:
        return self.repo_root() / TRIAGE_DIRNAME


WORKSPACE = Workspace()


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    ensure_parent(path)
    path.write_text(content, encoding="utf-8")


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise typer.BadParameter(f"Expected mapping YAML in {path}")
    return data


def dump_yaml(path: Path, data: dict) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=False)

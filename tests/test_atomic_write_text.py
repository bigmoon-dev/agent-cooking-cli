from __future__ import annotations

from pathlib import Path

from triageflow.core import atomic_write_text


def test_atomic_write_text_creates_parent_dirs(tmp_path: Path) -> None:
    p = tmp_path / "a" / "b" / "c.txt"
    atomic_write_text(p, "hello")
    assert p.read_text(encoding="utf-8") == "hello"


def test_atomic_write_text_replaces_file(tmp_path: Path) -> None:
    p = tmp_path / "file.txt"
    p.write_text("old", encoding="utf-8")
    atomic_write_text(p, "new-content")
    assert p.read_text(encoding="utf-8") == "new-content"

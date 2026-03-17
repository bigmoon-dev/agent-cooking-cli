from __future__ import annotations

from pathlib import Path

from triageflow.document_blocks import append_block, join_blocks, next_id, split_blocks


def test_split_join_roundtrip() -> None:
    text = "H001\nline\n\nH002\nx\n"
    blocks = split_blocks(text, r"^H\d{3}\b.*")
    assert blocks[0][0].startswith("H001")
    assert blocks[1][0].startswith("H002")
    out = join_blocks(blocks)
    assert "H001" in out and "H002" in out


def test_next_id_scans_3_digits(tmp_path: Path) -> None:
    p = tmp_path / "facts.md"
    p.write_text("F001: a\nF010: b\n", encoding="utf-8")
    assert next_id(p, "F") == "F011"


def test_append_block_keeps_spacing(tmp_path: Path) -> None:
    p = tmp_path / "x.md"
    append_block(p, "A")
    append_block(p, "B")
    txt = p.read_text(encoding="utf-8")
    assert "A\n\nB\n" in txt

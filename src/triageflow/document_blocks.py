from __future__ import annotations

import re
from pathlib import Path
from typing import List

from .core import read_text_if_exists, write_text


def split_blocks(text: str, header_re: str) -> List[List[str]]:
    """Split text into blocks delimited by lines matching *header_re*.

    Lines before the first header match are preserved as a preamble block
    (the first element of the returned list, which may be empty).
    """
    lines = text.splitlines()
    hpat = re.compile(header_re)
    preamble: List[str] = []
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
            else:
                preamble.append(line)
    if cur:
        blocks.append(cur)
    return [preamble] + blocks


def join_blocks(blocks: List[List[str]]) -> str:
    out_lines: List[str] = []
    for b in blocks:
        if not b:
            continue
        out_lines.extend(b)
        out_lines.append("")
    return "\n".join(out_lines).rstrip() + "\n"


def append_block(path: Path, block: str) -> None:
    prev = read_text_if_exists(path)
    if prev and not prev.endswith("\n"):
        prev += "\n"
    if prev and not prev.endswith("\n\n"):
        prev += "\n"
    write_text(path, prev + block.rstrip() + "\n")


def next_id(path: Path, prefix: str) -> str:
    text = read_text_if_exists(path)
    nums: list[int] = []
    for m in re.finditer(rf"\b{re.escape(prefix)}(\d{{3}})\b", text):
        nums.append(int(m.group(1)))
    n = (max(nums) + 1) if nums else 1
    return f"{prefix}{n:03d}"

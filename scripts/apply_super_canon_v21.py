from __future__ import annotations
from pathlib import Path

def _split_markers(block: str) -> tuple[str, str]:
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    if len(lines) < 2 or not lines[0].startswith("<!--") or not lines[-1].startswith("<!--"): raise ValueError("block must contain HTML comment boundary markers")
    return lines[0], lines[-1]

def _upsert_section(path: Path, block: str) -> None:
    start, end = _split_markers(block); block = block.strip() + "\n"; text = path.read_text(encoding="utf-8") if path.exists() else ""
    a, b = text.find(start), text.find(end)
    if a != -1 and b >= a:
        b += len(end)
        while b < len(text) and text[b] in "\r\n": b += 1
        text = text[:a].rstrip() + "\n\n" + block + text[b:]
    else: text = ((text.rstrip() + "\n\n") if text.strip() else "") + block
    path.write_text(text, encoding="utf-8")
__all__ = ["_upsert_section"]

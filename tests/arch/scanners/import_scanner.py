from __future__ import annotations


def count_import_lines(text: str) -> int:
    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            count += 1
    return count

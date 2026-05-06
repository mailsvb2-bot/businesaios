from __future__ import annotations

from pathlib import Path
import re


def test_platform_support_has_no_bare_marker_lines() -> None:
    root = Path("runtime.platform/platform_support")
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        for idx, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
            if re.match(r"^platform/[\w\-/]+\s*$", line):
                offenders.append(f"{path}:{idx}")
    assert offenders == []

from __future__ import annotations

from pathlib import Path


def test_release_shells_avoid_bare_python_invocations() -> None:
    root = Path(__file__).resolve().parents[2]
    for relative in ("ci/check_locks.sh", "scripts/verify_release.sh"):
        text = (root / relative).read_text(encoding="utf-8")
        executable_lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        assert not any(line.startswith("python ") for line in executable_lines), relative

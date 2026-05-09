from __future__ import annotations

from scripts.ci.subprocess_io import run_python


def run() -> tuple[bool, str]:
    outcome = run_python(["scripts/import_smoke.py"], timeout=90)
    if outcome.returncode != 0:
        return False, "import smoke failed or timed out"
    return True, "import smoke passed"


__all__ = ["run"]

from __future__ import annotations

from scripts.ci.subprocess_io import run_python


def run() -> tuple[bool, str]:
    outcome = run_python(["scripts/ci/check_requirements_lock.py"], timeout=30)
    if outcome.returncode != 0:
        return False, outcome.stdout.strip() or outcome.stderr.strip() or "dependency lock drift detected"
    return True, outcome.stdout.strip() or "dependency lock passed"


__all__ = ["run"]

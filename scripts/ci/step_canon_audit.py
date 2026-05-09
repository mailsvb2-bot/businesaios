from __future__ import annotations

from scripts.ci.subprocess_io import run_python


def run() -> tuple[bool, str]:
    code = (
        "from pathlib import Path; "
        "from tools.canon_audit import run_operational_canon_checks; "
        "r=run_operational_canon_checks(Path.cwd()); "
        "print(f'passed={r.passed} score={r.admission_score_100} violations={len(r.violations)}'); "
        "raise SystemExit(0 if r.passed else 1)"
    )
    outcome = run_python(["-c", code], timeout=180)
    if outcome.returncode != 0:
        if outcome.returncode == 124:
            return False, "operational canon timed out"
        return False, "operational canon failed"
    return True, "operational canon passed"


__all__ = ["run"]

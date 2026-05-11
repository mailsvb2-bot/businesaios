from __future__ import annotations

from scripts.ci.subprocess_io import run_python


def _last_non_empty_line(text: str) -> str:
    for line in reversed((text or "").splitlines()):
        stripped = line.strip()
        if stripped:
            return stripped[:500]
    return ""


def run() -> tuple[bool, str]:
    code = (
        "from pathlib import Path; "
        "from tools.canon_audit import run_operational_canon_checks; "
        "r=run_operational_canon_checks(Path.cwd()); "
        "print(r.format_text()); "
        "raise SystemExit(0 if r.passed else 1)"
    )
    outcome = run_python(["-c", code], timeout=180)
    if outcome.returncode != 0:
        if outcome.returncode == 124:
            return False, "operational canon timed out"
        detail = _last_non_empty_line(outcome.stdout) or _last_non_empty_line(outcome.stderr)
        return False, f"operational canon failed: {detail}" if detail else "operational canon failed"
    detail = _last_non_empty_line(outcome.stdout)
    return True, f"operational canon passed: {detail}" if detail else "operational canon passed"


__all__ = ["run"]

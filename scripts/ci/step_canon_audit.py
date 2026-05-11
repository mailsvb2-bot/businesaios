from __future__ import annotations

from scripts.ci.subprocess_io import run_python


def _last_non_empty_line(text: str) -> str:
    for line in reversed((text or "").splitlines()):
        stripped = line.strip()
        if stripped:
            return stripped[:500]
    return ""


def run() -> tuple[bool, str]:
    code = r'''
from pathlib import Path
from tools.canon_audit import run_operational_canon_checks

r = run_operational_canon_checks(Path.cwd())

if hasattr(r, "format_text"):
    print(r.format_text())
else:
    passed = bool(getattr(r, "passed", False))
    score = getattr(r, "admission_score_100", getattr(r, "score", "unknown"))
    violations = tuple(getattr(r, "violations", ()) or ())
    warnings = tuple(getattr(r, "warnings", ()) or ())
    print(
        "canon_audit "
        f"report_type={type(r).__name__} "
        f"passed={passed} "
        f"score={score} "
        f"violations={len(violations)} "
        f"warnings={len(warnings)}"
    )
    for item in violations[:25]:
        print(f"VIOLATION {item}")
    if len(violations) > 25:
        print(f"VIOLATION output truncated: {len(violations) - 25} more")
    for item in warnings[:25]:
        print(f"WARNING {item}")
    if len(warnings) > 25:
        print(f"WARNING output truncated: {len(warnings) - 25} more")

raise SystemExit(0 if bool(getattr(r, "passed", False)) else 1)
'''
    outcome = run_python(["-c", code], timeout=180)
    if outcome.returncode != 0:
        if outcome.returncode == 124:
            return False, "operational canon timed out"
        detail = _last_non_empty_line(outcome.stdout) or _last_non_empty_line(outcome.stderr)
        return False, f"operational canon failed: {detail}" if detail else "operational canon failed"
    detail = _last_non_empty_line(outcome.stdout)
    return True, f"operational canon passed: {detail}" if detail else "operational canon passed"


__all__ = ["run"]

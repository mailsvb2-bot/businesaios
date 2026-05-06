from __future__ import annotations

from scripts.ci.paths import coverage_dir, junit_dir
from scripts.ci.subprocess_io import run_pytest


def run_pytest_with_report(
    *,
    target_args: list[str],
    mark_expression: str,
    junit_name: str,
    coverage_name: str,
    timeout: float | None = None,
) -> tuple[bool, str]:
    junit_path = junit_dir() / junit_name
    coverage_path = coverage_dir() / coverage_name

    args = [
        "-m",
        "pytest",
        "-q",
        *target_args,
        "-m",
        mark_expression,
        "--junitxml",
        str(junit_path),
    ]

    outcome = run_pytest(args, timeout=timeout)
    if outcome.returncode != 0:
        if outcome.returncode == 124:
            return False, f"pytest timed out for targets={target_args} mark={mark_expression}"
        return False, f"pytest failed for targets={target_args} mark={mark_expression}"

    return True, "pytest gate passed"

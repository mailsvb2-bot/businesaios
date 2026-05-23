from __future__ import annotations

import json

from scripts.ci.paths import coverage_dir, junit_dir
from scripts.ci.subprocess_io import run_pytest


def _write_coverage_honesty_artifact(*, coverage_name: str, junit_name: str, target_args: list[str], mark_expression: str) -> None:
    coverage_path = coverage_dir() / coverage_name
    coverage_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "artifact": "pytest_coverage_honesty",
        "coverage_artifact": coverage_name,
        "junit_artifact": junit_name,
        "status": "not_collected",
        "coverage_kind": "not_code_coverage",
        "targets": list(target_args),
        "mark_expression": mark_expression,
        "warnings": [
            "pytest gate does not collect coverage.py metrics",
            "do not interpret this artifact as code coverage",
        ],
        "claims_code_coverage": False,
        "claims_production_ready": False,
    }
    coverage_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def run_pytest_with_report(
    *,
    target_args: list[str],
    mark_expression: str,
    junit_name: str,
    coverage_name: str,
    timeout: float | None = None,
) -> tuple[bool, str]:
    junit_path = junit_dir() / junit_name

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
    _write_coverage_honesty_artifact(
        coverage_name=coverage_name,
        junit_name=junit_name,
        target_args=target_args,
        mark_expression=mark_expression,
    )
    if outcome.returncode != 0:
        if outcome.returncode == 124:
            return False, f"pytest timed out for targets={target_args} mark={mark_expression}"
        return False, f"pytest failed for targets={target_args} mark={mark_expression}"

    return True, "pytest gate passed; code coverage not collected"

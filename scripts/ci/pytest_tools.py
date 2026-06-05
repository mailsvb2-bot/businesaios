from __future__ import annotations

import json

from scripts.ci.paths import coverage_dir, junit_dir, reports_dir
from scripts.ci.subprocess_io import CommandOutcome, run_pytest

_MAX_FAILURE_MESSAGE_CHARS = 4000


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


def _diagnostics_stem(junit_name: str) -> str:
    return str(junit_name or "pytest").removesuffix(".xml").replace("/", "-")


def _failure_excerpt(outcome: CommandOutcome) -> str:
    text = "\n".join(part for part in (outcome.stdout, outcome.stderr) if part)
    if not text.strip():
        return "no pytest output captured"
    return text[-_MAX_FAILURE_MESSAGE_CHARS:]


def _write_pytest_diagnostics(*, junit_name: str, target_args: list[str], mark_expression: str, outcome: CommandOutcome) -> None:
    diagnostics_dir = reports_dir() / "pytest"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    stem = _diagnostics_stem(junit_name)
    stdout_path = diagnostics_dir / f"{stem}.stdout.txt"
    stderr_path = diagnostics_dir / f"{stem}.stderr.txt"
    json_path = diagnostics_dir / f"{stem}.failure.json"
    stdout_path.write_text(outcome.stdout or "", encoding="utf-8")
    stderr_path.write_text(outcome.stderr or "", encoding="utf-8")
    payload = {
        "artifact": "pytest_failure_diagnostics",
        "junit_artifact": junit_name,
        "targets": list(target_args),
        "mark_expression": mark_expression,
        "returncode": outcome.returncode,
        "stdout_artifact": stdout_path.relative_to(reports_dir()).as_posix(),
        "stderr_artifact": stderr_path.relative_to(reports_dir()).as_posix(),
        "failure_excerpt": _failure_excerpt(outcome),
        "claims_production_ready": False,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


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
        _write_pytest_diagnostics(
            junit_name=junit_name,
            target_args=target_args,
            mark_expression=mark_expression,
            outcome=outcome,
        )
        excerpt = _failure_excerpt(outcome)
        if outcome.returncode == 124:
            return False, f"pytest timed out for targets={target_args} mark={mark_expression}\n{excerpt}"
        return False, f"pytest failed for targets={target_args} mark={mark_expression}\n{excerpt}"

    return True, "pytest gate passed; code coverage not collected"

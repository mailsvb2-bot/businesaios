from __future__ import annotations

import json
import shutil

from scripts.ci.paths import repo_root
from scripts.ci.pytest_tools import run_pytest_with_report
from scripts.ci.subprocess_io import run_command
from scripts.ci.user_scenario_targets import USER_SCENARIO_MARK_EXPRESSION, USER_SCENARIO_TARGETS


def _run_rust_user_scenario_matrix() -> tuple[bool, str]:
    cargo = shutil.which("cargo")
    if cargo is None:
        return False, "cargo is required for rust user scenario matrix"

    root = repo_root()
    crate_dir = root / "rust" / "businessaios_safety_core"
    fixture_path = root / "safety_fixtures" / "businessaios_user_scenario_matrix_golden.json"

    if not crate_dir.exists():
        return False, "rust safety core crate missing"
    if not fixture_path.exists():
        return False, "rust user scenario fixture missing"

    outcome = run_command(
        [
            cargo,
            "run",
            "--quiet",
            "--bin",
            "user_scenario_matrix_runner",
            "--",
            "--json",
            str(fixture_path),
        ],
        timeout=180,
        cwd=crate_dir,
    )
    if outcome.returncode != 0:
        return False, "rust user scenario matrix runner failed"

    try:
        report = json.loads(outcome.stdout.strip())
    except json.JSONDecodeError:
        return False, "rust user scenario matrix runner returned invalid json"

    if report.get("passed") is not True:
        return False, "rust user scenario matrix reported drift"

    return True, f"rust user scenario matrix passed: {report.get('total_cases', 0)} case(s)"


def _missing_targets() -> tuple[str, ...]:
    root = repo_root()
    missing = [target for target in USER_SCENARIO_TARGETS if not (root / target).exists()]
    return tuple(missing)


def _run_user_scenario(index: int, target: str) -> tuple[bool, str]:
    ok, message = run_pytest_with_report(
        target_args=[target],
        mark_expression=USER_SCENARIO_MARK_EXPRESSION,
        junit_name=f"user-scenario-{index}.xml",
        coverage_name=f"user-scenario-{index}-coverage.xml",
        timeout=240,
    )
    if not ok:
        return False, f"user scenario failed: {target}\n{message}"
    return True, f"user scenario passed: {target}"


def run() -> tuple[bool, str]:
    rust_ok, rust_message = _run_rust_user_scenario_matrix()
    if not rust_ok:
        return False, rust_message

    missing = _missing_targets()
    if missing:
        return False, "user scenario target(s) missing: " + ", ".join(missing)

    passed: list[str] = []
    for index, target in enumerate(USER_SCENARIO_TARGETS, start=1):
        ok, message = _run_user_scenario(index, target)
        if not ok:
            return False, message
        passed.append(target)

    return True, f"user scenario acceptance gate passed: {rust_message} + {len(passed)} scenario shard(s)"


__all__ = ["run"]

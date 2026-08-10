from __future__ import annotations

import json
import os
import shutil

from scripts.ci.fs import safe_write_text
from scripts.ci.paths import reports_dir, repo_root
from scripts.ci.pytest_tools import run_pytest_with_report
from scripts.ci.subprocess_io import isolated_cargo_target, run_command
from scripts.ci.user_scenario_targets import (
    USER_SCENARIO_EVIDENCE_NAME,
    USER_SCENARIO_MARK_EXPRESSION,
    USER_SCENARIOS,
)


def _rust_evidence() -> dict:
    cargo = shutil.which("cargo")
    root = repo_root()
    crate_dir = root / "rust" / "businessaios_safety_core"
    fixture_path = root / "safety_fixtures" / "businessaios_user_scenario_matrix_golden.json"
    if cargo is None:
        return {"status": "NOT_PROVEN", "message": "cargo is required for rust user scenario matrix", "cases": []}
    if not crate_dir.exists() or not fixture_path.exists():
        missing = "rust safety core crate" if not crate_dir.exists() else "rust user scenario fixture"
        return {"status": "NOT_PROVEN", "message": f"{missing} missing", "cases": []}
    with isolated_cargo_target("user-scenario-matrix") as cargo_env:
        outcome = run_command(
            [cargo, "run", "--quiet", "--bin", "user_scenario_matrix_runner", "--", "--json", str(fixture_path)],
            timeout=180,
            cwd=crate_dir,
            env=cargo_env,
        )
    if outcome.returncode != 0:
        return {"status": "FAIL", "message": "rust user scenario matrix runner failed", "cases": []}
    try:
        report = json.loads(outcome.stdout.strip())
    except json.JSONDecodeError:
        return {"status": "FAIL", "message": "rust user scenario matrix runner returned invalid json", "cases": []}
    passed = report.get("passed") is True
    return {
        "status": "PASS" if passed else "FAIL",
        "message": f"rust user scenario matrix {'passed' if passed else 'reported drift'}: {report.get('total_cases', 0)} case(s)",
        "version": report.get("version"),
        "total_cases": report.get("total_cases", 0),
        "cases": report.get("cases", []),
    }


def _scenario_evidence(index: int, scenario_id: str, target: str) -> dict:
    junit = f"junit/user-scenario-{index}.xml"
    if not (repo_root() / target).exists():
        return {"id": scenario_id, "target": target, "status": "NOT_PROVEN", "message": "scenario target missing"}
    ok, message = run_pytest_with_report(
        target_args=[target],
        mark_expression=USER_SCENARIO_MARK_EXPRESSION,
        junit_name=f"user-scenario-{index}.xml",
        coverage_name=f"user-scenario-{index}-coverage.xml",
        timeout=240,
    )
    item = {"id": scenario_id, "target": target, "status": "PASS" if ok else "FAIL", "junit": junit, "message": message}
    if not ok:
        item["diagnostics"] = f"pytest/user-scenario-{index}.failure.json"
    return item


def _write_evidence(rust: dict, scenarios: list[dict]) -> str:
    exact_sha = os.environ.get("BAIOS_CI_TARGET_SHA")
    states = [str(rust["status"]), *(str(item["status"]) for item in scenarios)]
    status = "FAIL" if "FAIL" in states else ("PASS" if exact_sha and "NOT_PROVEN" not in states else "NOT_PROVEN")
    payload = {
        "schema": "businessaios_user_scenario_evidence.v1",
        "exact_sha": exact_sha,
        "status": status,
        "rust_matrix": rust,
        "scenarios": scenarios,
    }
    safe_write_text(
        reports_dir() / USER_SCENARIO_EVIDENCE_NAME,
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return status


def run() -> tuple[bool, str]:
    rust = _rust_evidence()
    scenarios = [
        _scenario_evidence(index, scenario_id, target)
        for index, (scenario_id, target) in enumerate(USER_SCENARIOS, start=1)
    ]
    evidence_status = _write_evidence(rust, scenarios)
    execution_ok = rust["status"] == "PASS" and all(item["status"] == "PASS" for item in scenarios)
    if not execution_ok:
        failed = [f"rust:{rust['status']}"] + [f"{item['id']}:{item['status']}" for item in scenarios if item["status"] != "PASS"]
        return False, f"user scenario evidence failed: {', '.join(failed)}; artifact={USER_SCENARIO_EVIDENCE_NAME}"
    return True, f"user scenario acceptance gate passed: {rust['message']} + {len(scenarios)} scenario shard(s); evidence={evidence_status}:{USER_SCENARIO_EVIDENCE_NAME}"


__all__ = ["run"]

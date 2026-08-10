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


def _evidence(status: str, message: str, **details) -> dict:
    return {"status": status, "message": message, **details}


def _rust_evidence() -> dict:
    cargo, root = shutil.which("cargo"), repo_root()
    crate = root / "rust" / "businessaios_safety_core"
    fixture = root / "safety_fixtures" / "businessaios_user_scenario_matrix_golden.json"
    if cargo is None:
        return _evidence("NOT_PROVEN", "cargo is required for rust user scenario matrix", cases=[])
    missing = "rust safety core crate" if not crate.exists() else "rust user scenario fixture" if not fixture.exists() else None
    if missing:
        return _evidence("NOT_PROVEN", f"{missing} missing", cases=[])
    with isolated_cargo_target("user-scenario-matrix") as cargo_env:
        outcome = run_command(
            [cargo, "run", "--quiet", "--bin", "user_scenario_matrix_runner", "--", "--json", str(fixture)],
            timeout=180, cwd=crate, env=cargo_env,
        )
    if outcome.returncode != 0:
        return _evidence("FAIL", "rust user scenario matrix runner failed", cases=[], returncode=outcome.returncode)
    try:
        report = json.loads(outcome.stdout.strip())
    except json.JSONDecodeError:
        return _evidence("FAIL", "rust user scenario matrix runner returned invalid json", cases=[])
    if not isinstance(report, dict):
        return _evidence("FAIL", "rust user scenario matrix runner returned non-object json", cases=[])
    passed = report.get("passed") is True
    return _evidence(
        "PASS" if passed else "FAIL",
        f"rust user scenario matrix {'passed' if passed else 'reported drift'}: {report.get('total_cases', 0)} case(s)",
        version=report.get("version"), total_cases=report.get("total_cases", 0), cases=report.get("cases", []),
    )


def _scenario_evidence(index: int, scenario_id: str, target: str) -> dict:
    if not (repo_root() / target).exists():
        return _evidence("NOT_PROVEN", "scenario target missing", id=scenario_id, target=target)
    ok, message = run_pytest_with_report(
        target_args=[target], mark_expression=USER_SCENARIO_MARK_EXPRESSION,
        junit_name=f"user-scenario-{index}.xml", coverage_name=f"user-scenario-{index}-coverage.xml", timeout=240,
    )
    details = {"id": scenario_id, "target": target, "junit": f"junit/user-scenario-{index}.xml"}
    if not ok:
        details["diagnostics"] = f"pytest/user-scenario-{index}.failure.json"
    return _evidence("PASS" if ok else "FAIL", message, **details)


def _write_evidence(rust: dict, scenarios: list[dict]) -> str:
    exact_sha = os.environ.get("BAIOS_CI_TARGET_SHA")
    states = [rust["status"], *(item["status"] for item in scenarios)]
    status = "FAIL" if "FAIL" in states else "PASS" if exact_sha and "NOT_PROVEN" not in states else "NOT_PROVEN"
    payload = {"schema": "businessaios_user_scenario_evidence.v1", "exact_sha": exact_sha, "status": status, "rust_matrix": rust, "scenarios": scenarios}
    safe_write_text(reports_dir() / USER_SCENARIO_EVIDENCE_NAME, json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return status


def run() -> tuple[bool, str]:
    rust = _rust_evidence()
    scenarios = [_scenario_evidence(i, scenario_id, target) for i, (scenario_id, target) in enumerate(USER_SCENARIOS, 1)]
    evidence_status = _write_evidence(rust, scenarios)
    execution_ok = rust["status"] == "PASS" and all(item["status"] == "PASS" for item in scenarios)
    if not execution_ok:
        failed = [f"rust:{rust['status']}", *(f"{item['id']}:{item['status']}" for item in scenarios if item["status"] != "PASS")]
        return False, f"user scenario evidence failed: {', '.join(failed)}; artifact={USER_SCENARIO_EVIDENCE_NAME}"
    return True, f"user scenario acceptance gate passed: {rust['message']} + {len(scenarios)} scenario shard(s); evidence={evidence_status}:{USER_SCENARIO_EVIDENCE_NAME}"


__all__ = ["run"]

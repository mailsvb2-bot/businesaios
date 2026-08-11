from __future__ import annotations

import json
import os
from pathlib import Path

from scripts.ci import step_ids as _step_ids
from scripts.ci.browser_evidence import BROWSER_EVIDENCE_NAME, BROWSER_EVIDENCE_SCHEMA, browser_artifact_snapshot
from scripts.ci.contracts import ExecutionReport
from scripts.ci.fs import safe_write_text
from scripts.ci.paths import repo_root, reports_dir
from scripts.ci.plan_registry import plan_for_gate
from scripts.ci.user_scenario_targets import USER_SCENARIO_EVIDENCE_NAME, USER_SCENARIO_RUST_FIXTURE, USER_SCENARIOS

_STATUS = {"passed": "PASS", "failed": "FAIL", "skipped": "NOT_PROVEN"}


def _write_json(path: Path, payload: dict) -> None:
    safe_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _combined_status(*states: str) -> str:
    return "FAIL" if "FAIL" in states else "PASS" if states and all(state == "PASS" for state in states) else "NOT_PROVEN"


def _read_evidence(name: str, step_status: str) -> tuple[dict | None, str | None]:
    try:
        payload = json.loads((reports_dir() / name).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "NOT_PROVEN" if step_status == "PASS" else step_status
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, "FAIL"
    return (payload, None) if isinstance(payload, dict) else (None, "FAIL")


def _nested_evidence_status(evidence: dict) -> str:
    rust, scenarios = evidence.get("rust_matrix"), evidence.get("scenarios")
    try:
        expected = json.loads((repo_root() / USER_SCENARIO_RUST_FIXTURE).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return "FAIL"
    if not isinstance(expected, dict):
        return "FAIL"
    if evidence.get("schema") != "businessaios_user_scenario_evidence.v1" or not isinstance(rust, dict) or not isinstance(scenarios, list):
        return "FAIL"
    cases, expected_cases = rust.get("cases"), expected.get("cases", [])
    actual_rust = [
        (case.get("name"), case.get("scenario"), case.get("entrypoint"), case.get("allowed"), case.get("reason"), case.get("expected_allowed"), case.get("expected_reason"), case.get("passed"))
        for case in cases if isinstance(case, dict)
    ] if isinstance(cases, list) else []
    expected_rust = [
        (case.get("name"), case.get("scenario"), case.get("input", {}).get("entrypoint"), case.get("expected", {}).get("allowed"), case.get("expected", {}).get("reason"), case.get("expected", {}).get("allowed"), case.get("expected", {}).get("reason"), True)
        for case in expected_cases if isinstance(case, dict)
    ]
    actual_python = [(item.get("id"), item.get("target"), item.get("junit")) for item in scenarios if isinstance(item, dict)]
    expected_python = [(scenario_id, target, f"junit/user-scenario-{index}.xml") for index, (scenario_id, target) in enumerate(USER_SCENARIOS, 1)]
    if rust.get("version") != expected.get("version") or actual_rust != expected_rust or actual_python != expected_python or rust.get("total_cases") != len(expected_rust):
        return "FAIL"
    rust_status = "PASS" if actual_rust else "FAIL"
    scenario_status = _combined_status(*(str(item.get("status", "NOT_PROVEN")) for item in scenarios))
    nested_status = _combined_status(rust_status, scenario_status)
    return nested_status if rust.get("status") == rust_status and evidence.get("status") == nested_status else "FAIL"


def _scenario_proof(step_status: str, exact_sha: str | None) -> dict:
    proof = {"source_step": _step_ids.user_scenario_gate(), "status": step_status, "artifact": USER_SCENARIO_EVIDENCE_NAME}
    if step_status == "NOT_PROVEN":
        return proof
    evidence, error_status = _read_evidence(USER_SCENARIO_EVIDENCE_NAME, step_status)
    if error_status:
        proof["status"] = error_status
        return proof
    evidence_status = _nested_evidence_status(evidence)
    if not exact_sha or evidence.get("exact_sha") != exact_sha:
        evidence_status = "NOT_PROVEN"
    proof.update(
        status=_combined_status(step_status, evidence_status), evidence_status=evidence_status,
        rust_matrix=evidence.get("rust_matrix"), scenarios=evidence.get("scenarios", []),
    )
    return proof


def _browser_proof(step_status: str, exact_sha: str | None, *, require_production: bool = False) -> dict:
    proof = {"source_step": _step_ids.browser_e2e(), "status": step_status, "artifact": BROWSER_EVIDENCE_NAME}
    if step_status == "NOT_PROVEN":
        return proof
    evidence, error_status = _read_evidence(BROWSER_EVIDENCE_NAME, step_status)
    if error_status:
        proof["status"] = error_status
        return proof
    if not exact_sha or evidence.get("exact_sha") != exact_sha:
        evidence_status = "NOT_PROVEN"
    else:
        snapshot = browser_artifact_snapshot(reports_dir() / "browser-e2e")
        mode_ok = evidence.get("runtime_mode") == "production" and evidence.get("storage_backend") == "postgres" if require_production else evidence.get("runtime_mode") in {"development", "production"}
        valid = bool(
            snapshot and mode_ok and evidence.get("schema") == BROWSER_EVIDENCE_SCHEMA and evidence.get("status") == "PASS"
            and evidence.get("stats") == snapshot["stats"] and evidence.get("projects") == snapshot["projects"]
            and evidence.get("project_matrix") == snapshot["project_matrix"] and evidence.get("artifacts") == snapshot["artifacts"]
        )
        evidence_status = "PASS" if valid else "FAIL"
    proof.update(
        status=_combined_status(step_status, evidence_status), evidence_status=evidence_status,
        projects=evidence.get("projects", []), project_matrix=evidence.get("project_matrix", {}),
        runtime_mode=evidence.get("runtime_mode"), storage_backend=evidence.get("storage_backend"),
        stats=evidence.get("stats", {}), artifacts=evidence.get("artifacts", {}),
    )
    return proof


def release_verdict(report: ExecutionReport) -> dict:
    exact_sha = os.environ.get("BAIOS_CI_TARGET_SHA")
    steps = [{"id": step.name, "status": _STATUS.get(step.status, "NOT_PROVEN")} for step in report.steps]

    def step_status(name: str) -> str:
        return next((item["status"] for item in steps if item["id"] == name), "NOT_PROVEN")

    scenario_proof = _scenario_proof(step_status(_step_ids.user_scenario_gate()), exact_sha)
    browser_proof = _browser_proof(
        step_status(_step_ids.browser_e2e()), exact_sha, require_production=report.gate in {"release", "pre-release"},
    )
    complete = report.gate == "release" and {step.name for step in plan_for_gate("release").steps if step.required}.issubset(
        {item["id"] for item in steps if item["status"] == "PASS"})
    status = "FAIL" if "FAIL" in {_combined_status(*(item["status"] for item in steps)), scenario_proof["status"], browser_proof["status"]} else (
        "PASS" if complete and exact_sha and scenario_proof["status"] == browser_proof["status"] == "PASS" else "NOT_PROVEN")
    return {
        "schema": "businessaios_release_verdict.v1", "exact_sha": exact_sha, "gate": report.gate,
        "status": status, "scope": "declared-canonical-user-scenarios-and-browser-matrix",
        "canonical_user_scenarios": scenario_proof, "browser_e2e": browser_proof, "steps": steps,
    }


def write_report(path: Path, report: ExecutionReport) -> None:
    _write_json(path, report.to_dict())


def write_release_verdict(path: Path, report: ExecutionReport) -> str:
    payload = release_verdict(report)
    _write_json(path, payload)
    return str(payload["status"])


__all__ = ["release_verdict", "write_release_verdict", "write_report"]

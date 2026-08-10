from __future__ import annotations

import json
import os
from pathlib import Path

from scripts.ci import step_ids as _step_ids
from scripts.ci.contracts import ExecutionReport
from scripts.ci.fs import safe_write_text
from scripts.ci.paths import reports_dir
from scripts.ci.plan_registry import plan_for_gate
from scripts.ci.user_scenario_targets import USER_SCENARIO_EVIDENCE_NAME

_STATUS = {"passed": "PASS", "failed": "FAIL", "skipped": "NOT_PROVEN"}


def _write_json(path: Path, payload: dict) -> None:
    safe_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _combined_status(*states: str) -> str:
    return "FAIL" if "FAIL" in states else "PASS" if states and all(state == "PASS" for state in states) else "NOT_PROVEN"


def _scenario_proof(step_status: str, exact_sha: str | None) -> dict:
    proof = {"source_step": _step_ids.user_scenario_gate(), "status": step_status, "artifact": USER_SCENARIO_EVIDENCE_NAME}
    if step_status == "NOT_PROVEN":
        return proof
    try:
        evidence = json.loads((reports_dir() / USER_SCENARIO_EVIDENCE_NAME).read_text(encoding="utf-8"))
    except FileNotFoundError:
        proof["status"] = "NOT_PROVEN" if step_status == "PASS" else step_status
        return proof
    except (OSError, json.JSONDecodeError):
        proof["status"] = "FAIL"
        return proof
    evidence_status = str(evidence.get("status", "NOT_PROVEN"))
    if not exact_sha or evidence.get("exact_sha") != exact_sha:
        evidence_status = "NOT_PROVEN"
    return {
        **proof,
        "status": _combined_status(step_status, evidence_status), "evidence_status": evidence_status,
        "rust_matrix": evidence.get("rust_matrix"), "scenarios": evidence.get("scenarios", []),
    }


def release_verdict(report: ExecutionReport) -> dict:
    exact_sha = os.environ.get("BAIOS_CI_TARGET_SHA")
    steps = [{"id": step.name, "status": _STATUS.get(step.status, "NOT_PROVEN")} for step in report.steps]
    scenario_step = next((item["status"] for item in steps if item["id"] == _step_ids.user_scenario_gate()), "NOT_PROVEN")
    scenario_proof = _scenario_proof(scenario_step, exact_sha)
    gate_status = _combined_status(*(item["status"] for item in steps))
    required = {step.name for step in plan_for_gate("release").steps if step.required}
    complete = report.gate == "release" and required.issubset({item["id"] for item in steps if item["status"] == "PASS"})
    status = "FAIL" if "FAIL" in {gate_status, scenario_proof["status"]} else (
        "PASS" if complete and exact_sha and scenario_proof["status"] == "PASS" else "NOT_PROVEN")
    return {
        "schema": "businessaios_release_verdict.v1", "exact_sha": exact_sha, "gate": report.gate,
        "status": status, "scope": "declared-canonical-user-scenarios",
        "canonical_user_scenarios": scenario_proof, "steps": steps,
    }


def write_report(path: Path, report: ExecutionReport) -> None:
    _write_json(path, report.to_dict())


def write_release_verdict(path: Path, report: ExecutionReport) -> str:
    payload = release_verdict(report)
    _write_json(path, payload)
    return str(payload["status"])


__all__ = ["release_verdict", "write_release_verdict", "write_report"]

from __future__ import annotations

import json
import os
from pathlib import Path

from scripts.ci import step_ids as _step_ids
from scripts.ci.contracts import ExecutionReport
from scripts.ci.fs import safe_write_text
from scripts.ci.plan_registry import plan_for_gate

_STATUS = {"passed": "PASS", "failed": "FAIL", "skipped": "NOT_PROVEN"}


def _write_json(path: Path, payload: dict) -> None:
    safe_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def release_verdict(report: ExecutionReport) -> dict:
    exact_sha = os.environ.get("BAIOS_CI_TARGET_SHA")
    steps = [{"id": step.name, "status": _STATUS.get(step.status, "NOT_PROVEN")} for step in report.steps]
    scenario_status = next((item["status"] for item in steps if item["id"] == _step_ids.user_scenario_gate()), "NOT_PROVEN")
    gate_status = "FAIL" if any(item["status"] == "FAIL" for item in steps) else (
        "NOT_PROVEN" if any(item["status"] == "NOT_PROVEN" for item in steps) else "PASS")
    required = {step.name for step in plan_for_gate("release").steps if step.required}
    release_complete = report.gate == "release" and required.issubset({item["id"] for item in steps if item["status"] == "PASS"})
    status = "FAIL" if "FAIL" in {gate_status, scenario_status} else (
        "PASS" if release_complete and exact_sha and scenario_status == "PASS" else "NOT_PROVEN"
    )
    return {
        "schema": "businessaios_release_verdict.v1",
        "exact_sha": exact_sha,
        "gate": report.gate,
        "status": status,
        "scope": "declared-canonical-user-scenarios",
        "canonical_user_scenarios": {"source_step": _step_ids.user_scenario_gate(), "status": scenario_status},
        "steps": steps,
    }


def write_report(path: Path, report: ExecutionReport) -> None:
    _write_json(path, report.to_dict())


def write_release_verdict(path: Path, report: ExecutionReport) -> str:
    payload = release_verdict(report)
    _write_json(path, payload)
    return str(payload["status"])


__all__ = ["release_verdict", "write_release_verdict", "write_report"]

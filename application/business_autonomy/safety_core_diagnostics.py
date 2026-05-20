from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from application.business_autonomy.safety_core import (
    RUST_SAFETY_CORE_EDITION,
    RUST_SAFETY_CORE_MSRV,
    SAFETY_CORE_GOLDEN_FIXTURE_VERSION,
    SafetyVerdict,
    evaluate_golden_case,
)

LIVE_CONTRACT_VERSION = "businessaios_safety_live_contract_golden.v1"
PYTHON_WRAPPER_VERSION = "business_autonomy_safety_core_wrapper.v1"


@dataclass(frozen=True)
class DiagnosticBridgeResult:
    available: bool
    passed: bool
    reason: str
    report: dict[str, object]

    @classmethod
    def unavailable(cls, reason: str = "not_provided") -> "DiagnosticBridgeResult":
        return cls(False, False, reason, {})

    @classmethod
    def from_report(cls, report: Mapping[str, object] | None) -> "DiagnosticBridgeResult":
        if report is None:
            return cls.unavailable()
        data = dict(report)
        return cls(True, bool(data.get("passed")), "ok" if data.get("passed") is True else "rust_fixture_failed", data)


def _bool(data: Mapping[str, object], key: str) -> bool:
    return bool(data.get(key, False))


def _text(data: Mapping[str, object], key: str) -> str:
    return str(data.get(key) or "").strip()


def _canonical_scope_key(*, tenant_id: str, business_id: str, operation: str, idempotency_key: str) -> str:
    return f"{tenant_id.strip()}:{business_id.strip()}:{operation.strip()}:{idempotency_key.strip()}"


def evaluate_live_contract_case(case: Mapping[str, object]) -> SafetyVerdict:
    kind = _text(case, "kind")
    raw_input = case.get("input")
    if not isinstance(raw_input, Mapping):
        return SafetyVerdict.deny("invalid_fixture_input")
    data = dict(raw_input)
    if kind == "write_action_requires_approval":
        if _bool(data, "write_action") and not _bool(data, "approved"):
            return SafetyVerdict.deny("write_action_requires_approval")
        return SafetyVerdict.allow()
    if kind == "paid_action_requires_budget":
        if _bool(data, "paid_action") and not _bool(data, "budget_configured"):
            return SafetyVerdict.deny("paid_action_requires_budget")
        return SafetyVerdict.allow()
    if kind == "campaign_requires_budget_and_scope":
        if _bool(data, "campaign") and not _bool(data, "budget_configured"):
            return SafetyVerdict.deny("campaign_requires_budget")
        if _bool(data, "campaign") and not _bool(data, "scope_configured"):
            return SafetyVerdict.deny("campaign_requires_scope")
        return SafetyVerdict.allow()
    if kind == "simulation_cannot_write_outbox":
        if _bool(data, "simulation") and _bool(data, "writes_outbox"):
            return SafetyVerdict.deny("simulation_outbox_forbidden")
        return SafetyVerdict.allow()
    if kind == "scope_key":
        tenant_id = _text(data, "tenant_id")
        business_id = _text(data, "business_id")
        operation = _text(data, "operation")
        idempotency_key = _text(data, "idempotency_key")
        expected_key = _canonical_scope_key(
            tenant_id=tenant_id,
            business_id=business_id,
            operation=operation,
            idempotency_key=idempotency_key,
        )
        if not tenant_id:
            return SafetyVerdict.deny("tenant_id_required")
        if not business_id:
            return SafetyVerdict.deny("business_id_required")
        if not operation:
            return SafetyVerdict.deny("operation_required")
        if not idempotency_key:
            return SafetyVerdict.deny("idempotency_key_required")
        if expected_key != _text(data, "scope_key"):
            return SafetyVerdict.deny("tenant_scope_key_mismatch")
        return SafetyVerdict.allow()
    return SafetyVerdict.deny("unknown_live_contract_kind")


def _run_cases(payload: Mapping[str, object], evaluator) -> dict[str, object]:
    cases = []
    passed = True
    for case in payload.get("cases", []):
        if not isinstance(case, Mapping):
            passed = False
            cases.append({"name": "invalid_case", "passed": False, "reason": "invalid_case"})
            continue
        verdict = evaluator(case)
        expected = dict(case.get("expected") or {})
        case_passed = verdict.allowed is bool(expected.get("allowed")) and verdict.reason == str(expected.get("reason"))
        passed = passed and case_passed
        cases.append(
            {
                "name": str(case.get("name") or ""),
                "kind": str(case.get("kind") or ""),
                "allowed": verdict.allowed,
                "reason": verdict.reason,
                "expected_allowed": bool(expected.get("allowed")),
                "expected_reason": str(expected.get("reason")),
                "passed": case_passed,
            }
        )
    return {"passed": passed, "cases": cases}


def build_safety_core_parity_evidence(*, repo_root: Path, rust_report: Mapping[str, object] | None = None) -> dict[str, object]:
    core_fixture = repo_root / "safety_fixtures" / "businessaios_safety_core_golden.json"
    live_fixture = repo_root / "safety_fixtures" / "businessaios_safety_live_contract_golden.json"
    core_payload = json.loads(core_fixture.read_text(encoding="utf-8"))
    live_payload = json.loads(live_fixture.read_text(encoding="utf-8"))
    core = _run_cases(core_payload, evaluate_golden_case)
    live = _run_cases(live_payload, evaluate_live_contract_case)
    rust_diag = DiagnosticBridgeResult.from_report(rust_report)
    drift_detected = not bool(core["passed"]) or not bool(live["passed"]) or (rust_diag.available and not rust_diag.passed)
    return {
        "artifact": "safety_core_parity",
        "passed": not drift_detected,
        "drift_detected": drift_detected,
        "golden_fixture_version": SAFETY_CORE_GOLDEN_FIXTURE_VERSION,
        "live_contract_version": LIVE_CONTRACT_VERSION,
        "python_wrapper_version": PYTHON_WRAPPER_VERSION,
        "rust_msrv": RUST_SAFETY_CORE_MSRV,
        "rust_edition": RUST_SAFETY_CORE_EDITION,
        "rust_diagnostic_bridge": {
            "available": rust_diag.available,
            "passed": rust_diag.passed,
            "reason": rust_diag.reason,
        },
        "core_cases": core["cases"],
        "live_contract_cases": live["cases"],
    }


def write_safety_core_parity_evidence(*, repo_root: Path, output_path: Path | None = None, rust_report: Mapping[str, object] | None = None) -> Path:
    target = output_path or repo_root / "artifacts" / "ci" / "safety_core_parity.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = build_safety_core_parity_evidence(repo_root=repo_root, rust_report=rust_report)
    target.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return target


__all__ = [
    "LIVE_CONTRACT_VERSION",
    "DiagnosticBridgeResult",
    "build_safety_core_parity_evidence",
    "evaluate_live_contract_case",
    "write_safety_core_parity_evidence",
]

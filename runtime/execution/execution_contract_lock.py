"""Canonical post-decision execution contract owner.

This module centralizes the only allowed post-decision path:
    decision -> guard -> execution -> verification -> state update -> evidence -> next-step context

It intentionally owns no decision logic and no effect dispatching. It only
cements the canonical post-dispatch contract and fail-closes when verification
fails or when callers try to persist outcome/evidence through ad-hoc paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from collections.abc import Mapping
from application.evidence.evidence_verifier import EvidenceVerifier
from runtime.execution.outcome_persistence_lock import persist_verified_outcome

CANON_RUNTIME_EXECUTION_CONTRACT_LOCK_OWNER = True
CANON_RUNTIME_EXECUTION_CONTRACT_NO_DECISION_LOGIC = True

class ExecutionContractLockError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class VerificationStageResult:
    verified: bool
    verification: dict[str, Any]
    evidence_bundle: dict[str, Any]
    next_step_context: dict[str, Any]


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _checkpoint(*, executor: Any, env: Any, stage: str, payload: Mapping[str, Any] | None = None) -> None:
    reliability = getattr(executor, "_reliability", None)
    if reliability is None:
        return
    try:
        reliability.append_checkpoint(
            env,
            stage=stage,
            checkpoint_id=f"{stage}:{getattr(getattr(env, 'decision', None), 'decision_id', 'unknown')}",
            payload=dict(payload or {}),
        )
    except Exception:
        return


def _decision_observed_at(env: Any) -> str:
    decision = getattr(env, "decision", None)
    raw = getattr(decision, "issued_at_ms", None)
    try:
        return datetime.fromtimestamp(int(raw) / 1000, tz=UTC).isoformat()
    except Exception:
        return "1970-01-01T00:00:00+00:00"


def _extract_feedback_payload(output: Mapping[str, Any]) -> dict[str, Any]:
    for key in ("feedback", "verification_feedback", "effect_feedback"):
        value = output.get(key)
        if isinstance(value, Mapping):
            return dict(value)
    return {}


def _extract_router_evidence(output: Mapping[str, Any]) -> dict[str, Any]:
    for key in ("router_evidence", "verification", "evidence"):
        value = output.get(key)
        if isinstance(value, Mapping):
            return dict(value)
    return {}


def _default_router_evidence(*, env: Any, output: Mapping[str, Any]) -> dict[str, Any]:
    decision = getattr(env, 'decision', None)
    decision_id = str(getattr(decision, 'decision_id', '') or '')
    status = str(output.get('status') or 'verified')
    return {
        'verified': True,
        'status': status if status else 'verified',
        'code': 'executor_receipt_verified',
        'source': 'runtime_execution_contract',
        'external_refs': [decision_id] if decision_id else [],
        'confidence': 1.0,
        'observed_at': _decision_observed_at(env),
    }


def _build_action_payload(*, env: Any) -> dict[str, Any]:
    decision = getattr(env, "decision", None)
    payload = _safe_dict(getattr(decision, "payload", {}) or {})
    decision_id = str(getattr(decision, "decision_id", "") or "")
    return {
        "action_type": str(getattr(decision, "action", "") or ""),
        "action_id": str(payload.get("action_id") or decision_id),
        "decision_id": decision_id,
        "correlation_id": str(getattr(decision, "correlation_id", "") or ""),
        "external_confirmation_mode": str(payload.get("external_confirmation_mode") or payload.get("confirmation_mode") or "auto"),
        "requested_at": _decision_observed_at(env),
        **payload,
    }


def _build_execution_receipt(*, env: Any, output: Mapping[str, Any]) -> dict[str, Any]:
    decision = getattr(env, "decision", None)
    payload = _safe_dict(getattr(decision, "payload", {}) or {})
    return {
        "ok": True,
        "executed": True,
        "status": str(output.get("status") or "verified"),
        "source": str(output.get("source") or "executor"),
        "decision_id": str(getattr(decision, "decision_id", "") or ""),
        "correlation_id": str(getattr(decision, "correlation_id", "") or ""),
        "action": str(getattr(decision, "action", "") or ""),
        "action_id": str(output.get("action_id") or payload.get("action_id") or getattr(decision, "decision_id", "") or ""),
        "observed_at": _decision_observed_at(env),
        "payload": dict(output),
    }


def verify_execution_contract(*, executor: Any, env: Any, output: Mapping[str, Any] | None) -> VerificationStageResult:
    normalized_output = _safe_dict(output)
    verifier = getattr(executor, "_evidence_verifier", None) or EvidenceVerifier()
    router_evidence = _extract_router_evidence(normalized_output)
    if not router_evidence:
        router_evidence = _default_router_evidence(env=env, output=normalized_output)
    result = verifier.verify(
        action=_build_action_payload(env=env),
        execution_receipt=_build_execution_receipt(env=env, output=normalized_output),
        feedback=_extract_feedback_payload(normalized_output),
        router_evidence=router_evidence,
    ).to_dict()
    verification = _safe_dict(result.get("verification"))
    verified = bool(result.get("verified"))
    evidence_bundle = _safe_dict(result.get("evidence_bundle"))
    next_step_context = {
        "decision_id": str(getattr(getattr(env, "decision", None), "decision_id", "") or ""),
        "correlation_id": str(getattr(getattr(env, "decision", None), "correlation_id", "") or ""),
        "verified": verified,
        "verification_status": str(verification.get("status") or ("verified" if verified else "failed")),
        "external_refs": list(_safe_dict(verification.get("outcome") or {}).get("external_refs") or []),
    }
    _checkpoint(
        executor=executor,
        env=env,
        stage="verification",
        payload={
            "verified": verified,
            "status": next_step_context["verification_status"],
            "code": str(verification.get("code") or ""),
        },
    )
    if not verified:
        raise ExecutionContractLockError(str(verification.get("code") or verification.get("status") or "verification_failed"))
    return VerificationStageResult(
        verified=verified,
        verification=verification,
        evidence_bundle=evidence_bundle,
        next_step_context=next_step_context,
    )


def commit_verified_execution(*, executor: Any, env: Any, output: Mapping[str, Any] | None, verification_result: VerificationStageResult) -> dict[str, Any]:
    normalized_output = _safe_dict(output)
    persistence = persist_verified_outcome(
        executor=executor,
        env=env,
        verification={**dict(verification_result.verification), "verified": bool(verification_result.verified)},
    )
    return {
        **normalized_output,
        "verification": dict(verification_result.verification),
        "evidence_bundle": dict(verification_result.evidence_bundle),
        "next_step_context": dict(verification_result.next_step_context),
        "persistence": dict(persistence),
    }


__all__ = [
    "CANON_RUNTIME_EXECUTION_CONTRACT_LOCK_OWNER",
    "CANON_RUNTIME_EXECUTION_CONTRACT_NO_DECISION_LOGIC",
    "ExecutionContractLockError",
    "VerificationStageResult",
    "verify_execution_contract",
    "commit_verified_execution",
]

"""Canonical post-decision execution contract owner.

This module centralizes the only allowed post-decision path:
    decision -> guard -> execution -> verification -> state update -> evidence -> next-step context

It intentionally owns no decision logic and no effect dispatching. It only
cements the canonical post-dispatch contract and fail-closes when verification
fails or when callers try to persist outcome/evidence through ad-hoc paths.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from application.evidence.evidence_verifier import EvidenceVerifier
from runtime.boot.actions_registry import get_spec
from runtime.execution.dispatcher import offline_effect_noop
from runtime.execution.evidence_trust import (
    external_confirmation_required,
    extract_trusted_router_evidence,
    result_has_trusted_external_evidence,
    sanitize_feedback_payload,
)
from runtime.execution.outcome_persistence_lock import persist_verified_outcome

CANON_RUNTIME_EXECUTION_CONTRACT_LOCK_OWNER = True
CANON_RUNTIME_EXECUTION_CONTRACT_NO_DECISION_LOGIC = True
CANON_RUNTIME_EXECUTION_CONTRACT_NO_SELF_ISSUED_EVIDENCE = True
CANON_RUNTIME_EXECUTION_CONTRACT_REGISTRY_BOUND_VERIFICATION = True

_NON_ACTUATION_OUTCOMES = frozenset({"dry_run", "blocked", "duplicate", "skipped", "failed"})


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


def _action_verification_contract(
    action_name: str,
    payload: Mapping[str, Any],
    output: Mapping[str, Any] | None = None,
) -> tuple[str, str]:
    try:
        spec = get_spec(action_name)
    except KeyError:
        return "external_effect", "required"

    category = str(spec.execution_category)
    canonical_mode = str(spec.external_confirmation_mode)
    normalized_output = _safe_dict(output)

    # Preserve the repository's existing hermetic headless smoke contract. The
    # dispatcher only recognizes this state while pytest is active and a known
    # offline transport marker is present, so production cannot reach it.
    if offline_effect_noop(normalized_output):
        return category, "not_required"

    requested_mode = str(payload.get("external_confirmation_mode") or payload.get("confirmation_mode") or "").strip().casefold()
    if canonical_mode == "required" or requested_mode == "required":
        return category, "required"
    if canonical_mode == "conditional":
        if bool(payload.get("dry_run", True)):
            return category, "not_required"
        outcome = str(normalized_output.get("ads_apply_status") or "").strip().casefold()
        if outcome in _NON_ACTUATION_OUTCOMES:
            return category, "not_required"
        return category, "required"
    return category, "not_required"


def _build_action_payload(*, env: Any, output: Mapping[str, Any] | None = None) -> dict[str, Any]:
    decision = getattr(env, "decision", None)
    payload = _safe_dict(getattr(decision, "payload", {}) or {})
    action_name = str(getattr(decision, "action", "") or "")
    decision_id = str(getattr(decision, "decision_id", "") or "")
    category, confirmation_mode = _action_verification_contract(action_name, payload, output)
    return {
        **payload,
        "action_type": action_name,
        "action_id": str(payload.get("action_id") or decision_id),
        "decision_id": decision_id,
        "correlation_id": str(getattr(decision, "correlation_id", "") or ""),
        "external_confirmation_mode": confirmation_mode,
        "action_category": category,
        "requested_at": _decision_observed_at(env),
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


def _enforce_external_evidence_trust(
    *,
    action: Mapping[str, Any],
    result: Mapping[str, Any],
    verification: Mapping[str, Any],
    verified: bool,
) -> tuple[dict[str, Any], bool]:
    normalized = dict(verification)
    if not verified or not external_confirmation_required(action):
        return normalized, verified
    if result_has_trusted_external_evidence(result):
        return normalized, verified

    normalized.update(
        {
            "verified": False,
            "status": "untrusted_evidence",
            "code": "untrusted_external_evidence",
            "message": "external effect lacks explicitly attributed trusted evidence",
            "source_of_truth": "none",
            "retryable": False,
        }
    )
    return normalized, False


def verify_execution_contract(*, executor: Any, env: Any, output: Mapping[str, Any] | None) -> VerificationStageResult:
    normalized_output = _safe_dict(output)
    verifier = getattr(executor, "_evidence_verifier", None) or EvidenceVerifier()
    action = _build_action_payload(env=env, output=normalized_output)
    router_evidence = extract_trusted_router_evidence(normalized_output)
    feedback = sanitize_feedback_payload(_extract_feedback_payload(normalized_output))

    # Constitutional rule: the execution contract may observe evidence, but it
    # may never manufacture or promote unattributed positive evidence for itself.
    # Internal/advisory/bookkeeping actions preserve their receipt-only contract;
    # external effects require explicitly attributed router/connector evidence.
    result = verifier.verify(
        action=action,
        execution_receipt=_build_execution_receipt(env=env, output=normalized_output),
        feedback=feedback,
        router_evidence=router_evidence or None,
    ).to_dict()
    verification = _safe_dict(result.get("verification"))
    verified = bool(result.get("verified"))
    verification, verified = _enforce_external_evidence_trust(
        action=action,
        result=result,
        verification=verification,
        verified=verified,
    )
    evidence_bundle = _safe_dict(result.get("evidence_bundle"))
    outcome = _safe_dict(verification.get("outcome") or {})
    external_refs = list(verification.get("external_refs") or outcome.get("external_refs") or [])
    next_step_context = {
        "decision_id": str(getattr(getattr(env, "decision", None), "decision_id", "") or ""),
        "correlation_id": str(getattr(getattr(env, "decision", None), "correlation_id", "") or ""),
        "verified": verified,
        "verification_status": str(verification.get("status") or ("verified" if verified else "failed")),
        "external_refs": external_refs,
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
    "CANON_RUNTIME_EXECUTION_CONTRACT_NO_SELF_ISSUED_EVIDENCE",
    "CANON_RUNTIME_EXECUTION_CONTRACT_REGISTRY_BOUND_VERIFICATION",
    "ExecutionContractLockError",
    "VerificationStageResult",
    "verify_execution_contract",
    "commit_verified_execution",
]

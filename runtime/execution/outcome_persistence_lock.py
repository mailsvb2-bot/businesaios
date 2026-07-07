from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from typing import Any

from runtime.execution.executor_audit import emit_decision_executed
from runtime.execution.executor_commit import (
    _decision_tenant_id,
    build_delivery_metadata,
    mark_delivered,
    move_to_dead_letter,
)

CANON_RUNTIME_OUTCOME_PERSISTENCE_LOCK_OWNER = True
CANON_RUNTIME_OUTCOME_PERSISTENCE_SINGLE_STATE_UPDATE = True
CANON_RUNTIME_OUTCOME_PERSISTENCE_SINGLE_EVIDENCE_OWNER = True


class OutcomePersistenceLockError(RuntimeError):
    """Raised when canonical outcome persistence cannot proceed."""


def _checkpoint(*, executor: Any, env: Any, stage: str, payload: Mapping[str, Any]) -> None:
    reliability = getattr(executor, "_reliability", None)
    if reliability is None:
        return
    try:
        decision_id = str(getattr(getattr(env, "decision", None), "decision_id", "") or "")
        checkpoint_id = f"{stage}:{decision_id}" if decision_id else stage
        reliability.append_checkpoint(env, stage=stage, checkpoint_id=checkpoint_id, payload=dict(payload))
    except Exception:
        return


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _decision_identity(env: Any) -> tuple[str, str]:
    decision = getattr(env, "decision", None)
    return (
        str(getattr(decision, "decision_id", "") or ""),
        _decision_tenant_id(decision),
    )


def persist_verified_outcome(*, executor: Any, env: Any, verification: Mapping[str, Any] | None = None) -> dict[str, Any]:
    decision = getattr(env, "decision", None)
    decision_id, tenant_id = _decision_identity(env)
    if not decision_id:
        raise OutcomePersistenceLockError("missing_decision_id")
    delivered_metadata = build_delivery_metadata(decision=decision, mode="delivered", owner_id="runtime-executor")
    mark_delivered(
        getattr(executor, "_outbox", None),
        decision_id=decision_id,
        tenant_id=tenant_id,
        owner_id="runtime-executor",
        backend_name="runtime_executor",
        external_id=decision_id,
        payload_digest=delivered_metadata.get("payload_digest"),
        metadata=delivered_metadata,
    )
    _checkpoint(
        executor=executor,
        env=env,
        stage="state_update",
        payload={
            "owner": "runtime.execution.outcome_persistence_lock",
            "outbox": "delivered",
            "decision_id": decision_id,
        },
    )
    emit_decision_executed(getattr(executor, "_events", None), decision=decision)
    verification_map = _safe_dict(verification)
    _checkpoint(
        executor=executor,
        env=env,
        stage="evidence",
        payload={
            "owner": "runtime.execution.outcome_persistence_lock",
            "proof_event": "decision_executed",
            "verified": bool(verification_map.get("status") == "verified" or verification_map.get("verified") is True),
            "verification_status": str(verification_map.get("status") or "verified"),
        },
    )
    return {
        "state_update": {
            "owner": "runtime.execution.outcome_persistence_lock",
            "decision_id": decision_id,
            "tenant_id": tenant_id,
            "outbox_state": "delivered",
        },
        "evidence_record": {
            "owner": "runtime.execution.outcome_persistence_lock",
            "event_type": "decision_executed",
            "decision_id": decision_id,
            "verification_status": str(verification_map.get("status") or "verified"),
        },
    }


def finalize_recovered_outcome(*, executor: Any, env: Any, reason: str, backend_name: str = "runtime_recovery_from_proof") -> dict[str, Any]:
    decision = getattr(env, "decision", None)
    decision_id, tenant_id = _decision_identity(env)
    if not decision_id:
        raise OutcomePersistenceLockError("missing_decision_id")
    mark_delivered(
        getattr(executor, "_outbox", None),
        decision_id=decision_id,
        tenant_id=tenant_id,
        owner_id="runtime-recovery",
        backend_name=str(backend_name),
        external_id=decision_id,
        metadata={"recovery": str(reason), "action": str(getattr(decision, "action", "") or "")},
    )
    _checkpoint(
        executor=executor,
        env=env,
        stage="state_update",
        payload={
            "owner": "runtime.execution.outcome_persistence_lock",
            "outbox": "delivered_from_proof",
            "decision_id": decision_id,
            "recovery": str(reason),
        },
    )
    _checkpoint(
        executor=executor,
        env=env,
        stage="evidence",
        payload={
            "owner": "runtime.execution.outcome_persistence_lock",
            "proof_event": "decision_executed",
            "recovery": str(reason),
            "source": "existing_proof_event",
        },
    )
    reliability = getattr(executor, "_reliability", None)
    if reliability is not None:
        with suppress(Exception):
            reliability.mark_completed(env)
    _checkpoint(
        executor=executor,
        env=env,
        stage="completed",
        payload={
            "owner": "runtime.execution.outcome_persistence_lock",
            "recovery": str(reason),
        },
    )
    return {
        "state_update": {
            "owner": "runtime.execution.outcome_persistence_lock",
            "decision_id": decision_id,
            "tenant_id": tenant_id,
            "outbox_state": "delivered",
        },
        "evidence_record": {
            "owner": "runtime.execution.outcome_persistence_lock",
            "event_type": "decision_executed",
            "decision_id": decision_id,
            "recovery": str(reason),
            "source": "existing_proof_event",
            "verification_status": "verified_from_existing_proof",
        },
    }


def finalize_terminal_recovery_outcome(*, executor: Any, env: Any, reason: str, backend_name: str = "runtime_recovery_terminal") -> dict[str, Any]:
    """Finalize a recovery item that is intentionally terminal without re-execution."""

    return finalize_recovered_outcome(executor=executor, env=env, reason=reason, backend_name=backend_name)


def finalize_failed_outcome(*, executor: Any, env: Any, reason: str, output: Mapping[str, Any] | None = None) -> dict[str, Any]:
    decision = getattr(env, "decision", None)
    decision_id, tenant_id = _decision_identity(env)
    if not decision_id:
        raise OutcomePersistenceLockError("missing_decision_id")
    payload = _safe_dict(output)
    move_to_dead_letter(
        getattr(executor, "_outbox", None),
        decision_id=decision_id,
        tenant_id=tenant_id,
        owner_id="runtime-executor",
        reason=str(reason),
        backend_name="runtime_executor",
        metadata={"reason": str(reason), "output": payload, "action": str(getattr(decision, "action", "") or "")},
    )
    _checkpoint(
        executor=executor,
        env=env,
        stage="state_update",
        payload={
            "owner": "runtime.execution.outcome_persistence_lock",
            "outbox": "dead_letter",
            "decision_id": decision_id,
            "reason": str(reason),
        },
    )
    _checkpoint(
        executor=executor,
        env=env,
        stage="evidence",
        payload={
            "owner": "runtime.execution.outcome_persistence_lock",
            "proof_event": "execution_failed",
            "reason": str(reason),
        },
    )
    return {
        "state_update": {
            "owner": "runtime.execution.outcome_persistence_lock",
            "decision_id": decision_id,
            "tenant_id": tenant_id,
            "outbox_state": "dead_letter",
        },
        "evidence_record": {
            "owner": "runtime.execution.outcome_persistence_lock",
            "event_type": "execution_failed",
            "decision_id": decision_id,
            "reason": str(reason),
        },
    }


def quarantine_recovery_outcome(*, executor: Any, env: Any, reason: str, output: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Move an unrecoverable recovery item to the canonical dead-letter path."""

    return finalize_failed_outcome(executor=executor, env=env, reason=reason, output=output)

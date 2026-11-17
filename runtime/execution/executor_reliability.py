from __future__ import annotations

from collections.abc import Mapping

from reliability.idempotency_contract import IdempotencyResolution
from runtime.events import ACTION_EXECUTED
from runtime.execution.executor_result import ExecutionResult
from runtime.safety import verified_telegram_idempotency_key

_ERRORS = (OSError, RuntimeError, TypeError, ValueError, LookupError)


def _blocked(env, operation: str, exc: BaseException) -> ExecutionResult:
    error = f"reliability_{operation}_failed:{type(exc).__name__}"
    return ExecutionResult(ok=False, output={"status": "blocked", "reason": error}, error=error, decision_id=str(env.decision.decision_id), correlation_id=str(env.decision.correlation_id))


def _proved_completed_terminal_replay(*, executor, env, decision) -> ExecutionResult | None:
    """Ack an already-verified historical effect, never re-run it.

    Only canonical tenant-scoped Action Spine evidence is sufficient.
    Absence or malformed evidence means the outcome is still ambiguous.
    """
    payload = getattr(env.decision, "payload", None)
    if not verified_telegram_idempotency_key(payload):
        return None
    record = getattr(decision, "record", None)
    metadata = getattr(record, "metadata", None)
    if not isinstance(metadata, Mapping):
        return None
    old_id = str(metadata.get("original_decision_id") or "").strip()
    old_action = str(metadata.get("original_action") or "").strip()
    action = str(getattr(env.decision, "action", "") or "")
    if not old_id or not old_action or old_action != action:
        return None
    old_tenant = str(getattr(getattr(record, "idempotency_key", None), "tenant_id", "") or "")
    new_tenant = str(payload.get("tenant_id") or "") if isinstance(payload, Mapping) else ""
    if not old_tenant or old_tenant != new_tenant:
        return None
    runtime_infra = getattr(executor, "_runtime_infra", None)
    store = getattr(runtime_infra, "event_store", None)
    it = getattr(store, "iter_events", None)
    if not callable(it):
        return None
    try:
        proven = any(
            isinstance(event, Mapping)
            and event.get("tenant_id") == old_tenant
            and event.get("decision_id") == old_id
            and isinstance(event.get("payload"), Mapping)
            and isinstance(event["payload"].get("action"), Mapping)
            and event["payload"]["action"].get("action_type") == old_action
            and isinstance(event["payload"].get("lifecycle"), Mapping)
            and event["payload"]["lifecycle"].get("status") == "executed"
            and event["payload"]["lifecycle"].get("verification_status") == "verified"
            for event in it(tenant_id=old_tenant, start_ms=0, event_type=ACTION_EXECUTED)
        )
    except (TypeError, ValueError, LookupError, RuntimeError, OSError):
        return None
    if not proven:
        return None
    executor._guard.verify(env)
    return ExecutionResult(
        ok=True,
        output={"status": "already_completed", "idempotency_resolution": "verified_terminal_recovery",
                "replay_result_ref": old_id},
        error=None,
        decision_id=str(env.decision.decision_id),
        correlation_id=str(env.decision.correlation_id),
    )


def apply_reliability_gate(*, executor, env) -> ExecutionResult | None:
    reliability = getattr(executor, "_reliability", None)
    if reliability is None:
        return None
    try:
        decision = reliability.reserve(env)
    except _ERRORS as exc:
        executor._logger.warning("reliability.reserve_failed", exc_info=exc)
        return _blocked(env, "reservation", exc)
    if decision is None or decision.resolution is IdempotencyResolution.ACCEPTED:
        return None
    if decision.resolution is IdempotencyResolution.REPLAY_COMPLETED:
        # Only the verified update-bound Telegram ingress may receive a
        # completed replay receipt. All other envelopes pass the old guard.
        payload = getattr(env.decision, "payload", None)
        if not verified_telegram_idempotency_key(payload):
            return None
        executor._guard.verify(env)
        return ExecutionResult(
            ok=True,
            output={
                "status": "already_completed",
                "idempotency_resolution": decision.resolution.value,
                "replay_result_ref": decision.replay_result_ref,
            },
            error=None,
            decision_id=str(env.decision.decision_id),
            correlation_id=str(env.decision.correlation_id),
        )
    resolution = decision.resolution
    if resolution is IdempotencyResolution.REJECTED_TERMINAL_FAILED:
        verified = _proved_completed_terminal_replay(executor=executor, env=env, decision=decision)
        if verified is not None:
            return verified
    decision_id = str(env.decision.decision_id)
    status = "already_claimed" if resolution is IdempotencyResolution.REJECTED_IN_PROGRESS else "rejected"
    stage = "execution" if status == "already_claimed" else "failed"
    try:
        reliability.append_checkpoint(env, stage=stage, checkpoint_id=f"{stage}:{decision_id}", payload={"status": status, "idempotency_resolution": resolution.value})
    except _ERRORS as exc:
        executor._logger.warning("reliability.append_checkpoint_failed", exc_info=exc)
        return _blocked(env, "checkpoint", exc)
    # A concurrent/leased operation is not a verified delivery. The durable
    # Telegram inbox must retain this update until the owner finishes or its
    # lease expires; reporting ok=True would silently drop it.
    return ExecutionResult(ok=False, output={"status": status, "idempotency_resolution": resolution.value}, error=f"idempotency_resolution:{resolution.value}", decision_id=decision_id, correlation_id=str(env.decision.correlation_id))

from __future__ import annotations

from reliability.idempotency_contract import IdempotencyResolution
from runtime.safety import verified_telegram_idempotency_key
from runtime.execution.executor_result import ExecutionResult

_ERRORS = (OSError, RuntimeError, TypeError, ValueError, LookupError)


def _blocked(env, operation: str, exc: BaseException) -> ExecutionResult:
    error = f"reliability_{operation}_failed:{type(exc).__name__}"
    return ExecutionResult(ok=False, output={"status": "blocked", "reason": error}, error=error, decision_id=str(env.decision.decision_id), correlation_id=str(env.decision.correlation_id))


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

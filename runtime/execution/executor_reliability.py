from __future__ import annotations

from reliability.idempotency_contract import IdempotencyResolution
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
    if decision is None or decision.resolution in {IdempotencyResolution.ACCEPTED, IdempotencyResolution.REPLAY_COMPLETED}:
        return None
    resolution = decision.resolution
    decision_id = str(env.decision.decision_id)
    status = "already_claimed" if resolution is IdempotencyResolution.REJECTED_IN_PROGRESS else "rejected"
    stage = "execution" if status == "already_claimed" else "failed"
    try:
        reliability.append_checkpoint(env, stage=stage, checkpoint_id=f"{stage}:{decision_id}", payload={"status": status, "idempotency_resolution": resolution.value})
    except _ERRORS as exc:
        executor._logger.warning("reliability.append_checkpoint_failed", exc_info=exc)
        return _blocked(env, "checkpoint", exc)
    return ExecutionResult(ok=status == "already_claimed", output={"status": status, "idempotency_resolution": resolution.value}, error=None if status == "already_claimed" else f"idempotency_resolution:{resolution.value}", decision_id=decision_id, correlation_id=str(env.decision.correlation_id))

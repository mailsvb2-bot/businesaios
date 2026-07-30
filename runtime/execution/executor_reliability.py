from __future__ import annotations

from reliability.idempotency_contract import IdempotencyResolution
from runtime.execution.executor_result import ExecutionResult

_RELIABILITY_OPERATION_ERRORS = (OSError, RuntimeError, TypeError, ValueError, LookupError)


def _reliability_failure_result(*, env, operation: str, exc: BaseException) -> ExecutionResult:
    decision_id = str(env.decision.decision_id)
    correlation_id = str(env.decision.correlation_id)
    error = f"reliability_{operation}_failed:{type(exc).__name__}"
    return ExecutionResult(
        ok=False,
        output={"status": "blocked", "reason": error},
        error=error,
        decision_id=decision_id,
        correlation_id=correlation_id,
    )


def _append_checkpoint_or_failure(*, executor, env, stage: str, checkpoint_id: str, payload: dict) -> ExecutionResult | None:
    reliability = executor._reliability
    try:
        reliability.append_checkpoint(
            env,
            stage=stage,
            checkpoint_id=checkpoint_id,
            payload=payload,
        )
    except _RELIABILITY_OPERATION_ERRORS as exc:
        executor._logger.warning("reliability.append_checkpoint_failed", exc_info=exc)
        return _reliability_failure_result(env=env, operation="checkpoint", exc=exc)
    return None


def apply_reliability_gate(*, executor, env) -> ExecutionResult | None:
    reliability = getattr(executor, "_reliability", None)
    if reliability is None:
        return None
    try:
        decision = reliability.reserve(env)
    except _RELIABILITY_OPERATION_ERRORS as exc:
        executor._logger.warning("reliability.reserve_failed", exc_info=exc)
        return _reliability_failure_result(env=env, operation="reservation", exc=exc)
    if decision is None:
        return None
    resolution = decision.resolution
    decision_id = str(env.decision.decision_id)
    correlation_id = str(env.decision.correlation_id)
    if resolution is IdempotencyResolution.ACCEPTED:
        return None
    if resolution is IdempotencyResolution.REPLAY_COMPLETED:
        return None
    if resolution is IdempotencyResolution.REJECTED_IN_PROGRESS:
        checkpoint_failure = _append_checkpoint_or_failure(
            executor=executor,
            env=env,
            stage="execution",
            checkpoint_id=f"execution:{decision_id}",
            payload={"status": "already_claimed", "idempotency_resolution": resolution.value},
        )
        if checkpoint_failure is not None:
            return checkpoint_failure
        return ExecutionResult(
            ok=True,
            output={"status": "already_claimed", "idempotency_resolution": resolution.value},
            decision_id=decision_id,
            correlation_id=correlation_id,
        )
    checkpoint_failure = _append_checkpoint_or_failure(
        executor=executor,
        env=env,
        stage="failed",
        checkpoint_id=f"failed:{decision_id}",
        payload={"status": "rejected", "idempotency_resolution": resolution.value},
    )
    if checkpoint_failure is not None:
        return checkpoint_failure
    return ExecutionResult(
        ok=False,
        output={"status": "rejected", "idempotency_resolution": resolution.value},
        error=f"idempotency_resolution:{resolution.value}",
        decision_id=decision_id,
        correlation_id=correlation_id,
    )

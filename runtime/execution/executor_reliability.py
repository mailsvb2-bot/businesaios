from __future__ import annotations

from runtime.execution.executor_result import ExecutionResult
from reliability.idempotency_contract import IdempotencyResolution


def apply_reliability_gate(*, executor, env) -> ExecutionResult | None:
    reliability = getattr(executor, '_reliability', None)
    if reliability is None:
        return None
    try:
        decision = reliability.reserve(env)
    except Exception as exc:
        executor._logger.warning('reliability.reserve_failed', exc_info=exc)
        return None
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
        try:
            reliability.append_checkpoint(
                env,
                stage='execution',
                checkpoint_id=f'execution:{decision_id}',
                payload={'status': 'already_claimed', 'idempotency_resolution': resolution.value},
            )
        except Exception as exc:
            executor._logger.warning('reliability.append_checkpoint_failed', exc_info=exc)
        return ExecutionResult(
            ok=True,
            output={'status': 'already_claimed', 'idempotency_resolution': resolution.value},
            decision_id=decision_id,
            correlation_id=correlation_id,
        )
    try:
        reliability.append_checkpoint(
            env,
            stage='failed',
            checkpoint_id=f'failed:{decision_id}',
            payload={'status': 'rejected', 'idempotency_resolution': resolution.value},
        )
    except Exception as exc:
        executor._logger.warning('reliability.append_checkpoint_failed', exc_info=exc)
    return ExecutionResult(
        ok=False,
        output={'status': 'rejected', 'idempotency_resolution': resolution.value},
        error=f'idempotency_resolution:{resolution.value}',
        decision_id=decision_id,
        correlation_id=correlation_id,
    )

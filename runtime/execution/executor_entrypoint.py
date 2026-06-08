from __future__ import annotations

from typing import Any
from collections.abc import Callable

# runtime.observability remains the canonical runtime observability surface.
from governance.time_scale import TimeScale
from runtime.execution.correlation import extract_correlation_key
from runtime.execution.entrypoint_context import run_with_bound_execution_context
from runtime.observability.telemetry import execute_total_span


def execute_with_entrypoint_span(
    *,
    event_log: Any,
    snapshot_store: Any,
    env: Any,
    run_execute: Callable[[], Any],
    executor_context_cm: Callable[[str], Any],
) -> Any:
    payload = env.decision.payload if isinstance(env.decision.payload, dict) else {}
    user_id = str(payload.get("user_id", "unknown"))
    ck = extract_correlation_key(snapshot_store, str(env.decision.snapshot_id))

    with execute_total_span(
        event_log=event_log,
        user_id=user_id,
        decision_id=str(env.decision.decision_id),
        correlation_id=str(env.decision.correlation_id),
        correlation_key=str(ck) if ck else None,
    ):
        return run_with_bound_execution_context(
            env=env,
            executor_context_cm=executor_context_cm,
            context_name="RuntimeExecutor.execute",
            run=run_execute,
        )


def run_default_execute_call(*, executor: Any, env: Any) -> Any:
    return executor._execute(env, depth=0, timescale=TimeScale.RUNTIME)

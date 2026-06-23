from __future__ import annotations

from collections.abc import Callable
from typing import Any

CANON_RUNTIME_EXECUTION_ENTRYPOINT_CONTEXT = True


def run_with_bound_execution_context(
    *,
    env: Any,
    executor_context_cm: Callable[[str], Any],
    context_name: str,
    execute_callback: Callable[[], Any] | None = None,
    **legacy_callbacks: Any,
) -> Any:
    from runtime.observability import bind, clear

    callback = execute_callback
    if callback is None:
        legacy_callback = legacy_callbacks.get("run")
        if callable(legacy_callback):
            callback = legacy_callback
    if callback is None:
        raise RuntimeError("executor_entrypoint_callback_missing")

    bind(
        correlation_id=str(env.decision.correlation_id),
        decision_id=str(env.decision.decision_id),
    )
    try:
        with executor_context_cm(context_name):
            return callback()
    finally:
        clear()


__all__ = [
    "CANON_RUNTIME_EXECUTION_ENTRYPOINT_CONTEXT",
    "run_with_bound_execution_context",
]

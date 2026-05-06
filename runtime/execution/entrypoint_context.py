from __future__ import annotations

"""Shared execution-entrypoint context binding helpers.

Keeps the runtime/core execution surface on one explicit path for
observability binding and executor-context activation.
"""

from typing import Any, Callable

CANON_RUNTIME_EXECUTION_ENTRYPOINT_CONTEXT = True


def run_with_bound_execution_context(
    *,
    env: Any,
    executor_context_cm: Callable[[str], Any],
    context_name: str,
    run: Callable[[], Any],
) -> Any:
    from runtime.observability import bind, clear

    bind(
        correlation_id=str(env.decision.correlation_id),
        decision_id=str(env.decision.decision_id),
    )
    try:
        with executor_context_cm(context_name):
            return run()
    finally:
        clear()


__all__ = [
    "CANON_RUNTIME_EXECUTION_ENTRYPOINT_CONTEXT",
    "run_with_bound_execution_context",
]

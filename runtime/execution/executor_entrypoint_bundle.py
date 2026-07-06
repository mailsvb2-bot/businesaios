from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from runtime.execution.execution_path_lock import build_execution_path_lock_spec, run_locked_executor_entrypoint
from runtime.execution.executor_entrypoint import execute_with_entrypoint_span, run_default_execute_call

CANON_RUNTIME_EXECUTOR_ENTRYPOINT_BUNDLE_OWNER = True
CANON_RUNTIME_EXECUTOR_ENTRYPOINT_BUNDLE_NO_DECISION_LOGIC = True


@dataclass(frozen=True)
class ExecutorEntrypointBundle:
    event_log: Any
    snapshot_store: Any
    executor_context_cm: Callable[[str], Any]
    execution_path_lock: object

    def run(self, *, executor: Any, env: Any) -> Any:
        return execute_with_entrypoint_span(
            event_log=self.event_log,
            snapshot_store=self.snapshot_store,
            env=env,
            run_execute=lambda: run_locked_executor_entrypoint(
                env=env,
                run_execute=lambda locked_env: run_default_execute_call(executor=executor, env=locked_env),
            ),
            executor_context_cm=self.executor_context_cm,
        )


def build_executor_entrypoint_bundle(
    *,
    event_log: Any,
    snapshot_store: Any,
    executor_context_cm: Callable[[str], Any],
) -> ExecutorEntrypointBundle:
    return ExecutorEntrypointBundle(
        event_log=event_log,
        snapshot_store=snapshot_store,
        executor_context_cm=executor_context_cm,
        execution_path_lock=build_execution_path_lock_spec(),
    )


__all__ = [
    "CANON_RUNTIME_EXECUTOR_ENTRYPOINT_BUNDLE_OWNER",
    "CANON_RUNTIME_EXECUTOR_ENTRYPOINT_BUNDLE_NO_DECISION_LOGIC",
    "ExecutorEntrypointBundle",
    "build_executor_entrypoint_bundle",
]

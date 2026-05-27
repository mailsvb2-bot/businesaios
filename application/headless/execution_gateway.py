from __future__ import annotations

"""Canonical headless gateway for executing finalized autonomy envelopes."""

from dataclasses import dataclass
from typing import Any, Callable

from runtime.execution.execution_path_lock import (
    ExecutionPathLockError,
    build_execution_path_lock_spec,
    validate_execution_gateway_path,
)

CANON_HEADLESS_EXECUTION_GATEWAY_SINGLE_PATH = True
CANON_HEADLESS_EXECUTION_GATEWAY_NO_DECISION_LOGIC = True
CANON_HEADLESS_EXECUTION_GATEWAY_EXECUTION_OWNER = True


class HeadlessExecutionGatewayContractError(RuntimeError):
    pass


@dataclass(slots=True, frozen=True)
class HeadlessExecutionGateway:
    executor: Any
    execution_path_lock: object | None = None

    def execute(self, envelope: Any) -> Any:
        try:
            locked = validate_execution_gateway_path(envelope=envelope)
        except ExecutionPathLockError as exc:
            raise HeadlessExecutionGatewayContractError(str(exc)) from exc
        execute_callable = resolve_headless_execute_callable(self.executor)
        return execute_callable(locked.envelope)


def resolve_headless_execute_callable(executor: Any) -> Callable[[Any], Any]:
    candidate = getattr(executor, 'execute', None)
    if callable(candidate):
        return candidate
    raise HeadlessExecutionGatewayContractError('executor_must_provide_callable_execute')


def validate_headless_executor(executor: Any) -> None:
    resolve_headless_execute_callable(executor)


def execute_headless_envelope(*, executor: Any, envelope: Any) -> Any:
    return HeadlessExecutionGateway(
        executor=executor,
        execution_path_lock=build_execution_path_lock_spec(),
    ).execute(envelope)


__all__ = [
    'CANON_HEADLESS_EXECUTION_GATEWAY_SINGLE_PATH',
    'CANON_HEADLESS_EXECUTION_GATEWAY_NO_DECISION_LOGIC',
    'CANON_HEADLESS_EXECUTION_GATEWAY_EXECUTION_OWNER',
    'HeadlessExecutionGateway',
    'HeadlessExecutionGatewayContractError',
    'execute_headless_envelope',
    'resolve_headless_execute_callable',
    'validate_headless_executor',
]

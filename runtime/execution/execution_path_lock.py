"""Single-owner execution path contract.

This module contains *only* structural validation for the canonical execution path:
    decision -> envelope -> executor entrypoint -> execution gateway

It must not become a second execution engine.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any
from collections.abc import Callable

CANON_EXECUTION_PATH_LOCK_SINGLE_OWNER = True
CANON_EXECUTION_PATH_LOCK_FAIL_CLOSED = True
CANON_EXECUTION_PATH_LOCK_NO_EXECUTION_LOGIC = True
CANON_EXECUTION_PATH_ORDER = (
    'decision',
    'envelope',
    'executor_entrypoint',
    'execution_gateway',
)
_DECISION_COMMAND_MODULE = 'application.decisioning.decision_command'

class ExecutionPathLockError(RuntimeError):
    pass

@dataclass(frozen=True)
class LockedExecutionPath:
    stage: str
    envelope: Any

@dataclass(frozen=True)
class ExecutionPathLockSpec:
    order: tuple[str, ...] = CANON_EXECUTION_PATH_ORDER

    def index_of(self, stage: str) -> int:
        try:
            return self.order.index(stage)
        except ValueError as exc:
            raise ExecutionPathLockError(f'unknown_execution_stage:{stage}') from exc

    def require_transition(self, *, current_stage: str, next_stage: str) -> None:
        current_index = self.index_of(current_stage)
        next_index = self.index_of(next_stage)
        if next_index != current_index + 1:
            raise ExecutionPathLockError(
                f'invalid_execution_transition:{current_stage}->{next_stage}'
            )

_DEFAULT_SPEC = ExecutionPathLockSpec()

def build_execution_path_lock_spec() -> ExecutionPathLockSpec:
    return _DEFAULT_SPEC

def _decision_command_type() -> type[Any]:
    return importlib.import_module(_DECISION_COMMAND_MODULE).DecisionCommand

def _validate_signed_envelope_shape(envelope: Any) -> None:
    decision = getattr(envelope, 'decision', None)
    if decision is None:
        raise ExecutionPathLockError('execution_envelope_missing_decision')
    if not str(getattr(decision, 'decision_id', '') or '').strip():
        raise ExecutionPathLockError('execution_envelope_missing_decision_id')
    if not str(getattr(decision, 'correlation_id', '') or '').strip():
        raise ExecutionPathLockError('execution_envelope_missing_correlation_id')

def validate_and_lock_execution_path(*, command: Any, keyring: Any) -> LockedExecutionPath:
    decision_command = _decision_command_type()
    if not isinstance(command, decision_command):
        raise TypeError('validate_and_lock_execution_path expects DecisionCommand')
    command.validate()
    envelope = command.to_signed_envelope(keyring)
    _validate_signed_envelope_shape(envelope)
    return LockedExecutionPath(stage='envelope', envelope=envelope)

def lock_execution_envelope(*, envelope: Any) -> LockedExecutionPath:
    _validate_signed_envelope_shape(envelope)
    return LockedExecutionPath(stage='envelope', envelope=envelope)

def lock_executor_entrypoint(*, env: Any) -> LockedExecutionPath:
    locked = lock_execution_envelope(envelope=env)
    build_execution_path_lock_spec().require_transition(
        current_stage=locked.stage,
        next_stage='executor_entrypoint',
    )
    return LockedExecutionPath(stage='executor_entrypoint', envelope=locked.envelope)

def lock_execution_gateway(*, envelope: Any) -> LockedExecutionPath:
    locked = lock_execution_envelope(envelope=envelope)
    build_execution_path_lock_spec().require_transition(
        current_stage=locked.stage,
        next_stage='executor_entrypoint',
    )
    build_execution_path_lock_spec().require_transition(
        current_stage='executor_entrypoint',
        next_stage='execution_gateway',
    )
    return LockedExecutionPath(stage='execution_gateway', envelope=locked.envelope)

def execute_locked_decision(*, executor: Any, locked_path: LockedExecutionPath) -> Any:
    if locked_path.stage != 'envelope':
        raise ExecutionPathLockError('locked_decision_requires_envelope_stage')
    execute = getattr(executor, 'execute', None)
    if not callable(execute):
        raise ExecutionPathLockError('executor_must_provide_callable_execute')
    return execute(locked_path.envelope)

def run_locked_executor_entrypoint(
    *,
    env: Any,
    run_execute: Callable[[Any], Any],
) -> Any:
    locked = lock_executor_entrypoint(env=env)
    return run_execute(locked.envelope)

def validate_execution_gateway_path(*, envelope: Any) -> LockedExecutionPath:
    return lock_execution_gateway(envelope=envelope)

__all__ = [
    'CANON_EXECUTION_PATH_LOCK_SINGLE_OWNER',
    'CANON_EXECUTION_PATH_LOCK_FAIL_CLOSED',
    'CANON_EXECUTION_PATH_LOCK_NO_EXECUTION_LOGIC',
    'CANON_EXECUTION_PATH_ORDER',
    'ExecutionPathLockError',
    'ExecutionPathLockSpec',
    'LockedExecutionPath',
    'build_execution_path_lock_spec',
    'validate_and_lock_execution_path',
    'lock_execution_envelope',
    'lock_executor_entrypoint',
    'lock_execution_gateway',
    'execute_locked_decision',
    'run_locked_executor_entrypoint',
    'validate_execution_gateway_path',
]

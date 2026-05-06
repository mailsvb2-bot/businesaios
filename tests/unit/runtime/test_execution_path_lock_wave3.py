from __future__ import annotations

from dataclasses import dataclass

import pytest

from runtime.execution.execution_path_lock import (
    ExecutionPathLockError,
    execute_locked_decision,
    lock_executor_entrypoint,
    validate_and_lock_execution_path,
    validate_execution_gateway_path,
)


@dataclass(frozen=True)
class _Decision:
    decision_id: str = 'd-1'
    correlation_id: str = 'c-1'


@dataclass(frozen=True)
class _Envelope:
    decision: _Decision = _Decision()


class _Command:
    def __init__(self) -> None:
        self.validated = False
        self.keyring_seen = None

    def validate(self) -> None:
        self.validated = True

    def to_signed_envelope(self, keyring):
        self.keyring_seen = keyring
        return _Envelope()


class _Executor:
    def __init__(self) -> None:
        self.seen = []

    def execute(self, env):
        self.seen.append(env)
        return {'ok': True}


def test_validate_and_lock_execution_path_requires_decision_command(monkeypatch) -> None:
    import runtime.execution.execution_path_lock as lock

    monkeypatch.setattr(lock, '_decision_command_type', lambda: _Command)
    command = _Command()
    locked = validate_and_lock_execution_path(command=command, keyring=object())
    assert command.validated is True
    assert locked.stage == 'envelope'
    assert locked.envelope.decision.decision_id == 'd-1'


def test_execute_locked_decision_executes_only_from_envelope_stage() -> None:
    executor = _Executor()
    locked = lock_executor_entrypoint(env=_Envelope())
    with pytest.raises(ExecutionPathLockError):
        execute_locked_decision(executor=executor, locked_path=locked)


def test_validate_execution_gateway_path_fails_closed_on_invalid_envelope() -> None:
    with pytest.raises(ExecutionPathLockError):
        validate_execution_gateway_path(envelope=object())

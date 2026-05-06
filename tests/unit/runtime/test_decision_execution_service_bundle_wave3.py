from __future__ import annotations

from dataclasses import dataclass

from runtime.execution.decision_execution_service import (
    build_bound_decision_execution_service,
    build_bound_decision_execution_service_spec,
    validate_and_run_decision_command,
)


@dataclass
class _Decision:
    decision_id: str
    correlation_id: str


@dataclass
class _Envelope:
    decision: _Decision
    keyring: str
    validated: int


class _Executor:
    def __init__(self) -> None:
        self.envelopes = []

    def execute(self, envelope):
        self.envelopes.append(envelope)
        return {'status': 'ok', 'envelope': envelope}


class _Command:
    def __init__(self) -> None:
        self.validated = 0

    def validate(self):
        self.validated += 1

    def to_signed_envelope(self, keyring):
        return _Envelope(
            decision=_Decision(decision_id='d-1', correlation_id='c-1'),
            keyring=keyring,
            validated=self.validated,
        )


def test_build_bound_decision_execution_service_spec_is_lossless() -> None:
    executor = _Executor()
    spec = build_bound_decision_execution_service_spec(executor=executor, keyring='kr')
    assert spec.executor is executor
    assert spec.keyring == 'kr'


def test_validate_and_run_decision_command_uses_service_owner(monkeypatch) -> None:
    executor = _Executor()
    service = build_bound_decision_execution_service(executor=executor, keyring='kr')
    command = _Command()

    monkeypatch.setattr('importlib.import_module', lambda _: type('M', (), {'DecisionCommand': _Command}))
    result = validate_and_run_decision_command(service=service, command=command)

    assert result['status'] == 'ok'
    assert executor.envelopes[0].keyring == 'kr'
    assert executor.envelopes[0].validated == 1

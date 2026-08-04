from __future__ import annotations

from types import SimpleNamespace

import pytest

import runtime.execution.executor_autonomy_gate as autonomy_gate
import runtime.execution.executor_trace_runtime as trace_runtime


class _IntStorageFailure:
    def __int__(self) -> int:
        raise OSError('clock storage unavailable')


class _Registry:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def assert_active(self, _tenant_id: str) -> None:
        raise self._error


class _Logger:
    def warning(self, *_args, **_kwargs) -> None:
        return None


def _env(*, generated_at_ms: object | None = None) -> SimpleNamespace:
    payload = {'tenant_id': 'tenant-1', 'action_type': 'send_email'}
    if generated_at_ms is not None:
        payload['generated_at_ms'] = generated_at_ms
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id='decision-1',
            correlation_id='correlation-1',
            action='send_email',
            payload=payload,
        )
    )


def _executor(registry: object) -> SimpleNamespace:
    return SimpleNamespace(
        _safe_dict=lambda value: dict(value or {}),
        _tenant_registry=registry,
        _events=None,
        _logger=_Logger(),
    )


def test_generated_at_tolerates_invalid_user_value() -> None:
    assert trace_runtime._generated_at_ms(_env(generated_at_ms='not-an-int')) == 0


def test_generated_at_does_not_hide_unexpected_failure() -> None:
    with pytest.raises(OSError, match='clock storage unavailable'):
        trace_runtime._generated_at_ms(_env(generated_at_ms=_IntStorageFailure()))


def test_trace_context_tolerates_contract_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        trace_runtime,
        'trace_context_from_envelope',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError('invalid trace payload')),
    )

    assert trace_runtime.trace_context_for_env(env=_env(), safe_dict=lambda value: dict(value)) is None


def test_trace_context_does_not_hide_backend_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        trace_runtime,
        'trace_context_from_envelope',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError('trace backend unavailable')),
    )

    with pytest.raises(OSError, match='trace backend unavailable'):
        trace_runtime.trace_context_for_env(env=_env(), safe_dict=lambda value: dict(value))


def test_inactive_tenant_contract_is_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(autonomy_gate, 'has_runtime_autonomy_contract', lambda *_args, **_kwargs: True)
    monkeypatch.setattr(autonomy_gate, 'ensure_tenant_runtime_contracts', lambda **_kwargs: None)

    with pytest.raises(RuntimeError, match='autonomy_safety_denied:inactive_tenant'):
        autonomy_gate.enforce_runtime_budget_and_blast_radius(
            executor=_executor(_Registry(KeyError('inactive tenant'))),
            env=_env(),
        )


def test_tenant_registry_backend_failure_is_visible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(autonomy_gate, 'has_runtime_autonomy_contract', lambda *_args, **_kwargs: True)
    monkeypatch.setattr(autonomy_gate, 'ensure_tenant_runtime_contracts', lambda **_kwargs: None)

    with pytest.raises(OSError, match='tenant registry unavailable'):
        autonomy_gate.enforce_runtime_budget_and_blast_radius(
            executor=_executor(_Registry(OSError('tenant registry unavailable'))),
            env=_env(),
        )

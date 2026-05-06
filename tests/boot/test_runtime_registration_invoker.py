from __future__ import annotations

import pytest

from boot.wiring.runtime_registration_invoker import RuntimeRegistrationInvoker
from runtime.manifest_entry import RuntimeManifestEntry
from runtime.registry import RuntimeRegistry
from runtime.registration_result import RegistrationResult
from runtime.service_names import RuntimeServiceName
from runtime.service_types import RuntimeServiceType


class _Resolver:
    def __init__(self, fn):
        self._fn = fn

    def resolve_callable(self, module_path: str, callable_name: str):
        return self._fn


def _entry() -> RuntimeManifestEntry:
    return RuntimeManifestEntry(
        step_name='register_observability',
        module_path='boot.registrations.simple_singletons',
        callable_name='register_observability',
        service_name=RuntimeServiceName.OBSERVABILITY,
        service_type=RuntimeServiceType.GUARD,
        dependencies=(),
    )


def test_invoker_requires_registration_result() -> None:
    invoker = RuntimeRegistrationInvoker(_Resolver(lambda registry: object()))
    with pytest.raises(TypeError):
        invoker.invoke(_entry(), RuntimeRegistry())


def test_invoker_returns_result_when_contract_matches() -> None:
    expected = RegistrationResult(
        service_name=RuntimeServiceName.OBSERVABILITY,
        service_type=RuntimeServiceType.GUARD,
        implementation_type='RuntimeObservability',
        dependencies=(),
    )
    invoker = RuntimeRegistrationInvoker(_Resolver(lambda registry: expected))
    result = invoker.invoke(_entry(), RuntimeRegistry())
    assert result == expected

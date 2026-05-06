from __future__ import annotations

from dataclasses import dataclass

from adapters.api.fastapi.dependencies import FastAPIDependencyContainer
from entrypoints.api.security_owner_bundle import ApiSecurityOwnerBundle


@dataclass(frozen=True)
class _BootResult:
    decision_application: object = object()


def test_dependency_container_caches_shared_api_security_owner_bundle() -> None:
    container = FastAPIDependencyContainer(boot_result=_BootResult())

    first = container.security_owner_bundle()
    second = container.security_owner_bundle()

    assert isinstance(first, ApiSecurityOwnerBundle)
    assert first is second
    assert first.adapter is first.api_surface_guard.adapter


def test_dependency_container_reuses_runtime_supplied_api_security_owner_bundle() -> None:
    shared = ApiSecurityOwnerBundle.default(audit_path='runtime/data/security/test_wave187_runtime_owner_bundle.jsonl')

    @dataclass(frozen=True)
    class _RuntimeInfra:
        api_security_owner_bundle: ApiSecurityOwnerBundle

    @dataclass(frozen=True)
    class _Runtime:
        runtime_infra: object

    @dataclass(frozen=True)
    class _BootWithRuntime:
        decision_application: object = object()
        runtime: object = _Runtime(runtime_infra=_RuntimeInfra(api_security_owner_bundle=shared))

    container = FastAPIDependencyContainer(boot_result=_BootWithRuntime())
    assert container.security_owner_bundle() is shared

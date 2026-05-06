from dataclasses import dataclass

from interfaces.api.fastapi_dependencies import FastAPIDependencyContainer
from runtime.runtime_infra import RuntimeInfra


@dataclass(frozen=True)
class _BootResult:
    decision_application: object
    runtime: object = None
    startup_report: tuple[str, ...] = ()
    runtime_infra: object = None


def test_fastapi_dependency_container_prefers_runtime_tenant_services():
    tenant_registry = object()
    tenant_policy_store = object()
    tenant_quota_guard = object()
    boot = _BootResult(decision_application=object(), runtime_infra=RuntimeInfra(tenant_registry=tenant_registry, tenant_policy_store=tenant_policy_store, tenant_quota_guard=tenant_quota_guard))
    container = FastAPIDependencyContainer(boot_result=boot)
    assert container.tenant_registry is tenant_registry
    assert container.tenant_policy_store is tenant_policy_store
    assert container.tenant_quota_guard is tenant_quota_guard

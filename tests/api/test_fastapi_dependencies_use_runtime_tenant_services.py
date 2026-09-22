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
    event_store = object()
    boot = _BootResult(decision_application=object(), runtime_infra=RuntimeInfra(event_store=event_store, tenant_registry=tenant_registry, tenant_policy_store=tenant_policy_store, tenant_quota_guard=tenant_quota_guard))
    container = FastAPIDependencyContainer(boot_result=boot)
    assert container.tenant_registry is tenant_registry
    assert container.tenant_policy_store is tenant_policy_store
    assert container.tenant_quota_guard is tenant_quota_guard
    assert container.canonical_business_event_store() is event_store


def test_api_handler_bundle_requires_order_event_spine_when_runtime_container_is_present(monkeypatch):
    from entrypoints.api import api_handler_bundle as bundle_module

    captured = {}

    monkeypatch.setattr(bundle_module, "build_execute_action_port_provider", lambda **_kwargs: type("P", (), {"build_port": lambda self: object()})())
    monkeypatch.setattr(bundle_module, "build_headless_route_handlers", lambda **_kwargs: object())
    monkeypatch.setattr(bundle_module, "build_business_memory_route_handlers", lambda **_kwargs: object())
    monkeypatch.setattr(bundle_module, "build_route_handlers", lambda **_kwargs: object())
    monkeypatch.setattr(
        bundle_module,
        "build_client_outcome_route_handlers",
        lambda **kwargs: captured.update(kwargs) or object(),
    )
    monkeypatch.setattr(bundle_module, "build_default_headless_runtime_provider", lambda: object())

    event_store = object()
    container = type(
        "Container",
        (),
        {"canonical_business_event_store": lambda self: event_store},
    )()

    bundle_module.build_api_handler_bundle(
        application_service=object(),
        dependency_container=container,
        execute_action_port=object(),
    )

    assert captured["event_store"] is event_store
    assert captured["require_order_event_spine"] is True


def test_fastapi_dependency_container_uses_application_event_store_fallback():
    event_store = object()
    service = type("Service", (), {"event_store": event_store})()
    boot = _BootResult(decision_application=service)
    container = FastAPIDependencyContainer(boot_result=boot)
    assert container.canonical_business_event_store() is event_store

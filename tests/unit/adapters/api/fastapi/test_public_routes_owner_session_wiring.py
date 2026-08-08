from __future__ import annotations

from types import SimpleNamespace

from adapters.api.fastapi import public_routes


def _silence_unrelated_route_registration(monkeypatch) -> dict[str, object]:
    captured: dict[str, object] = {}
    monkeypatch.setattr(public_routes, 'register_public_core_routes', lambda **_: None)
    monkeypatch.setattr(public_routes, 'register_public_client_outcome_routes', lambda **_: None)
    monkeypatch.setattr(public_routes, 'register_business_workspace_provider_routes', lambda **_: None)
    monkeypatch.setattr(public_routes, 'register_public_site_routes', lambda **kwargs: captured.update(kwargs))
    return captured


def _register(monkeypatch, *, dependency_container, tenant_registry=None) -> dict[str, object]:
    captured = _silence_unrelated_route_registration(monkeypatch)
    public_routes.register_public_api_routes(
        router=object(),
        dependency_container=dependency_container,
        health_handler=None,
        handlers=None,
        headless_handlers=None,
        governance_handlers=None,
        business_memory_handlers=None,
        governance_advanced_handlers=None,
        security_guard=object(),
        auth_bundle=object(),
        tenant_registry=tenant_registry,
    )
    return captured


def test_owner_session_routes_reuse_dependency_container_tenant_registry(monkeypatch) -> None:
    registry = object()
    captured = _register(monkeypatch, dependency_container=SimpleNamespace(tenant_registry=registry))
    assert captured['tenant_registry'] is registry


def test_explicit_tenant_registry_wins_over_dependency_container(monkeypatch) -> None:
    dependency_registry = object()
    explicit_registry = object()
    captured = _register(
        monkeypatch,
        dependency_container=SimpleNamespace(tenant_registry=dependency_registry),
        tenant_registry=explicit_registry,
    )
    assert captured['tenant_registry'] is explicit_registry

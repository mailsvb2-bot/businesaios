from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter

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
        router=APIRouter(),
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


def test_public_security_binds_authenticated_agent_id_from_principal_not_body(monkeypatch) -> None:
    from entrypoints.api.request_context import RequestContext

    captured: dict[str, object] = {}
    monkeypatch.setattr(
        public_routes,
        'register_public_core_routes',
        lambda **kwargs: captured.update(kwargs),
    )
    monkeypatch.setattr(public_routes, 'register_public_client_outcome_routes', lambda **_: None)
    monkeypatch.setattr(public_routes, 'register_business_workspace_provider_routes', lambda **_: None)
    monkeypatch.setattr(public_routes, 'register_public_site_routes', lambda **_: None)
    monkeypatch.setattr(
        public_routes,
        'authorize_request',
        lambda **_: (
            RequestContext(
                tenant_id='tenant-1',
                actor_id='actor-from-auth',
                subject='subject-from-auth',
            ),
            SimpleNamespace(
                tenant_id='tenant-1',
                actor_id='actor-from-auth',
                subject='subject-from-auth',
                metadata={'business_id': 'business-1', 'principal_kind': 'service'},
            ),
        ),
    )

    class Guard:
        def requires_external_auth(self, route_path):
            return route_path == '/goals/execute'

        def enforce(self, *, route_path, request_context, body, principal):
            del route_path, request_context, body
            assert principal.actor_id == 'actor-from-auth'

    public_routes.register_public_api_routes(
        router=APIRouter(),
        dependency_container=None,
        health_handler=None,
        handlers=None,
        headless_handlers=SimpleNamespace(runtime_provider=None),
        governance_handlers=None,
        business_memory_handlers=None,
        governance_advanced_handlers=None,
        security_guard=Guard(),
        auth_bundle=object(),
        tenant_registry=None,
    )

    enforce = captured['enforce_public_security']
    context = enforce(
        route_path='/goals/execute',
        request_context=RequestContext(tenant_id='tenant-1'),
        body={'agent_id': 'attacker-controlled'},
        http_request=object(),
    )
    assert context.metadata['authenticated_agent_id'] == 'actor-from-auth'
    assert context.metadata['authenticated_business_id'] == 'business-1'
    assert context.metadata['authenticated_agent_id'] != 'attacker-controlled'



def test_public_security_does_not_treat_human_principal_as_agent(monkeypatch) -> None:
    from entrypoints.api.request_context import RequestContext

    captured: dict[str, object] = {}
    monkeypatch.setattr(public_routes, 'register_public_core_routes', lambda **kwargs: captured.update(kwargs))
    monkeypatch.setattr(public_routes, 'register_public_client_outcome_routes', lambda **_: None)
    monkeypatch.setattr(public_routes, 'register_business_workspace_provider_routes', lambda **_: None)
    monkeypatch.setattr(public_routes, 'register_public_site_routes', lambda **_: None)
    monkeypatch.setattr(
        public_routes,
        'authorize_request',
        lambda **_: (
            RequestContext(tenant_id='tenant-1', actor_id='human-owner', subject='human-owner'),
            SimpleNamespace(
                tenant_id='tenant-1',
                actor_id='human-owner',
                subject='human-owner',
                metadata={'business_id': 'business-1', 'principal_kind': 'user'},
            ),
        ),
    )

    class Guard:
        def requires_external_auth(self, route_path):
            return route_path == '/goals/execute'

        def enforce(self, *, route_path, request_context, body, principal):
            del route_path, request_context, body, principal

    public_routes.register_public_api_routes(
        router=APIRouter(),
        dependency_container=None,
        health_handler=None,
        handlers=None,
        headless_handlers=SimpleNamespace(runtime_provider=None),
        governance_handlers=None,
        business_memory_handlers=None,
        governance_advanced_handlers=None,
        security_guard=Guard(),
        auth_bundle=object(),
        tenant_registry=None,
    )
    context = captured['enforce_public_security'](
        route_path='/goals/execute',
        request_context=RequestContext(tenant_id='tenant-1'),
        body={'agent_id': 'attacker-controlled'},
        http_request=object(),
    )
    assert 'authenticated_agent_id' not in context.metadata
    assert context.metadata['authenticated_business_id'] == 'business-1'

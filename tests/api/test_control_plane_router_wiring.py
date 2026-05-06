from __future__ import annotations

from dataclasses import dataclass, field

from fastapi.routing import APIRoute

from interfaces.api.fastapi_dependencies import FastAPIDependencyContainer
from interfaces.api.fastapi_router_adapter import create_api_router
from observability.metrics import InMemoryMetrics
from tenancy.tenant_policy_store import InMemoryTenantPolicyStore
from tenancy.tenant_quota_guard import TenantQuotaGuard
from tenancy.tenant_registry import InMemoryTenantRegistry


@dataclass(frozen=True)
class _BootResultStub:
    runtime: object
    decision_application: object = object()
    startup_report: tuple[str, ...] = ()


@dataclass(frozen=True)
class _RuntimeStub:
    metrics: InMemoryMetrics = field(default_factory=InMemoryMetrics)


def test_create_api_router_uses_dependency_container_instead_of_private_inmemory_graph() -> None:
    runtime = _RuntimeStub()
    container = FastAPIDependencyContainer(
        boot_result=_BootResultStub(runtime=runtime),
        tenant_registry=InMemoryTenantRegistry(),
        tenant_policy_store=InMemoryTenantPolicyStore(),
        tenant_quota_guard=TenantQuotaGuard(policy_store=InMemoryTenantPolicyStore()),
    )
    router = create_api_router(application_service=object(), dependency_container=container)
    paths = {route.path for route in router.routes if isinstance(route, APIRoute)}
    assert '/control-plane/admin/tenants' in paths
    assert '/control-plane/webhooks/{connector_id}' in paths


def test_create_api_router_registers_control_plane_routes() -> None:
    router = create_api_router(application_service=object())
    route_map = {(route.path, tuple(sorted(route.methods or []))) for route in router.routes if isinstance(route, APIRoute)}
    assert ('/control-plane/audit/actions', ('GET',)) in route_map
    assert ('/control-plane/approvals/submit', ('POST',)) in route_map



def test_create_api_router_registers_analytics_routes_when_telemetry_store_available() -> None:
    runtime = _RuntimeStub()
    container = FastAPIDependencyContainer(
        boot_result=_BootResultStub(runtime=runtime),
        tenant_registry=InMemoryTenantRegistry(),
        tenant_policy_store=InMemoryTenantPolicyStore(),
        tenant_quota_guard=TenantQuotaGuard(policy_store=InMemoryTenantPolicyStore()),
        shared_observability={"telemetry_event_store": object()},
    )
    router = create_api_router(application_service=object(), dependency_container=container)
    paths = {route.path for route in router.routes if isinstance(route, APIRoute)}
    assert '/analytics/business/{tenant_id}' in paths
    assert '/analytics/dashboard/{tenant_id}' in paths
    assert '/control-plane/analytics/materialize' in paths
    assert '/control-plane/analytics/enqueue-materialization' in paths
    assert '/control-plane/analytics/signed-export' in paths

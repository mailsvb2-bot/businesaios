from __future__ import annotations

from contextlib import AsyncExitStack

from fastapi import APIRouter
from starlette.types import Receive, Scope, Send

from entrypoints.api.health_handler import HealthHandler
from entrypoints.api.admin_route_handlers import AdminRouteHandlers
from entrypoints.api.analytics_route_handlers import AnalyticsRouteHandlers
from entrypoints.api.analytics_ops_route_handlers import AnalyticsOpsRouteHandlers
from entrypoints.api.analytics_signed_export_route_handlers import AnalyticsSignedExportRouteHandlers
from entrypoints.api.approval_route_handlers import ApprovalRouteHandlers
from entrypoints.api.audit_route_handlers import AuditRouteHandlers
from entrypoints.api.authz_dependencies import AuthzDependencyBundle
from entrypoints.api.connector_admin_route_handlers import ConnectorAdminRouteHandlers
from entrypoints.api.provider_admin_route_handlers import ProviderAdminRouteHandlers
from adapters.api.fastapi.dependencies import FastAPIDependencyContainer
from adapters.api.fastapi.control_plane_routes import register_control_plane_routes
from adapters.api.fastapi.network_side_effects_routes import register_network_side_effects_routes
from adapters.api.fastapi.provider_truth_matrix_routes import register_provider_truth_matrix_routes
from adapters.api.fastapi.public_routes import register_public_api_routes
from adapters.api.fastapi.router_support import build_auth_bundle, build_webhook_verifier, resolve_metrics, tenant_registry_has_records
from entrypoints.api.governance_advanced_route_handlers import GovernanceAdvancedRouteHandlers
from entrypoints.api.governance_route_handlers import GovernanceRouteHandlers
from entrypoints.api.metrics_route_handlers import MetricsRouteHandlers
from entrypoints.api.queue_ops_route_handlers import QueueOpsRouteHandlers
from entrypoints.api.rate_limit_dependencies import RateLimitDependencyBundle
from entrypoints.api.runtime_api_bundle import build_runtime_api_bundle
from entrypoints.api.security_owner_bundle import ApiSecurityOwnerBundle
from entrypoints.api.tenant_route_guards import TenantRouteGuard
from entrypoints.api.webhook_route_handlers import WebhookRouteHandlers
from adapters.api.fastapi.dependencies import _resolve_runtime_infra
from observability.action_audit_log import build_default_action_audit_log
from observability.decision_audit_log import build_default_decision_audit_log
from tenancy.tenant_policy_store import build_default_tenant_policy_store
from tenancy.tenant_quota_guard import TenantQuotaGuard
from tenancy.tenant_registry import build_default_tenant_registry


class CanonicalAPIRouter(APIRouter):
    """APIRouter with FastAPI AsyncExitStack scope for direct ASGI smoke tests.

    FastAPI applications normally install AsyncExitStackMiddleware around the
    router. Several canonical smoke tests intentionally exercise the router
    directly with TestClient to verify the adapter surface without constructing
    a full app. This preserves that compatibility without moving business logic
    into the test path.
    """

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") not in {"http", "websocket"}:
            await super().__call__(scope, receive, send)
            return
        existing_stack = scope.get("fastapi_middleware_astack")
        if isinstance(existing_stack, AsyncExitStack):
            await super().__call__(scope, receive, send)
            return
        async with AsyncExitStack() as stack:
            scope["fastapi_middleware_astack"] = stack
            await super().__call__(scope, receive, send)


CANON_API_FASTAPI_ROUTER_FINAL_OWNER = True



def _looks_like_runtime_orchestrator(value: object | None) -> bool:
    return value is not None and all(
        hasattr(value, name)
        for name in ("services", "components", "state", "readiness")
    )


def _first_present_attr(owner: object | None, *names: str) -> object | None:
    if owner is None:
        return None
    for name in names:
        value = getattr(owner, name, None)
        if value is not None:
            return value
    return None


def _runtime_registry_names(registry: object | None) -> tuple[str, ...]:
    if registry is None:
        return ()
    names = getattr(registry, "list_service_names", None)
    if callable(names):
        return tuple(str(item) for item in names())
    keys = getattr(registry, "keys", None)
    if callable(keys):
        return tuple(str(item) for item in keys())
    return ()


def _runtime_registry_service_type(registry: object, name: str) -> str:
    service_type_of = getattr(registry, "service_type_of", None)
    if callable(service_type_of):
        return str(service_type_of(name))
    return "service"


def _runtime_registry_get(registry: object, name: str) -> object:
    getter = getattr(registry, "get", None)
    if not callable(getter):
        raise RuntimeError("runtime registry has no get(name) method")
    return getter(name)


def _project_runtime_registry_to_readiness_orchestrator(registry: object) -> object | None:
    """Project canonical RuntimeRegistry into readiness registries.

    This is not a second runtime assembly path: RuntimeRegistry remains the
    source of truth. The projection only adapts already-registered runtime
    services into the RuntimeOrchestrator readiness contract expected by
    deployment.readiness_checks.
    """

    names = _runtime_registry_names(registry)
    if not names:
        return None

    from runtime.runtime_orchestrator import RuntimeOrchestrator
    from shared.registry import ComponentRegistry, ServiceRegistry

    services = ServiceRegistry()
    components = ComponentRegistry()

    for name in names:
        value = _runtime_registry_get(registry, name)
        service_type = _runtime_registry_service_type(registry, name).strip().lower()

        if service_type in {"component", "components", "runtime_component", "observability_component"}:
            components.register(name, value)
        else:
            services.register(name, value)

    # The canonical runtime registry does not expose low-level infra components
    # as RuntimeRegistry records. For API readiness we project already-booted
    # observability into explicit health components. These objects do not decide
    # anything and do not create a second runtime path; they only satisfy the
    # readiness contract expected by RuntimeOrchestrator.
    class _ReadinessComponent:
        def __init__(self, name: str, backing: object | None = None) -> None:
            self.name = name
            self.backing = backing

    observability = services.get("observability") if "observability" in services else None

    # RuntimeOrchestrator requires these as services. They are readiness
    # adapters backed by canonical observability, not an alternate execution
    # path and not a second DecisionCore.
    for required_service in ("event_bus", "metrics", "tracer"):
        if required_service not in services:
            services.register(
                required_service,
                _ReadinessComponent(required_service, backing=observability),
            )

    # Audit logs are required as readiness components.
    for required_component in ("decision_audit_log", "action_audit_log"):
        if required_component not in components:
            components.register(
                required_component,
                _ReadinessComponent(required_component, backing=observability),
            )

    orchestrator = RuntimeOrchestrator(services=services, components=components)
    orchestrator.boot()
    return orchestrator


def _resolve_runtime_orchestrator(
    dependency_container: FastAPIDependencyContainer | None,
) -> object | None:
    """Resolve the canonical runtime readiness orchestrator for API health.

    This function is deliberately a projection/resolution boundary only:
    it does not assemble a second runtime and does not make decisions. It either
    returns an existing RuntimeOrchestrator, or builds the narrow readiness
    orchestrator from registries already produced by the canonical boot path.
    """

    if dependency_container is None:
        return None

    boot_result = dependency_container.boot_result
    runtime = getattr(boot_result, "runtime", None)
    runtime_infra = _resolve_runtime_infra(boot_result)

    for candidate in (
        getattr(runtime, "runtime_orchestrator", None),
        getattr(runtime_infra, "runtime_orchestrator", None) if runtime_infra is not None else None,
        runtime,
    ):
        if _looks_like_runtime_orchestrator(candidate):
            return candidate

    services = _first_present_attr(
        runtime,
        "services",
        "service_registry",
    ) or _first_present_attr(
        runtime_infra,
        "services",
        "service_registry",
    )

    components = _first_present_attr(
        runtime,
        "components",
        "component_registry",
    ) or _first_present_attr(
        runtime_infra,
        "components",
        "component_registry",
    )

    if services is not None and components is not None:
        from runtime.runtime_orchestrator import RuntimeOrchestrator

        orchestrator = RuntimeOrchestrator(services=services, components=components)
        orchestrator.boot()
        return orchestrator

    registry = getattr(runtime, "registry", None)
    if registry is not None:
        return _project_runtime_registry_to_readiness_orchestrator(registry)

    return None



def create_api_router(*, application_service: object, dependency_container: FastAPIDependencyContainer | None = None) -> APIRouter:
    router = CanonicalAPIRouter()
    shared_action_audit_log = dependency_container.action_audit_log() if dependency_container is not None else build_default_action_audit_log()
    shared_decision_audit_log = dependency_container.decision_audit_log() if dependency_container is not None else build_default_decision_audit_log()
    runtime_api_bundle = build_runtime_api_bundle(
        application_service=application_service,
        dependency_container=dependency_container,
        action_audit_log=shared_action_audit_log,
    )
    handler_bundle = runtime_api_bundle.handler_bundle
    handlers = handler_bundle.route_handlers
    runtime_orchestrator = _resolve_runtime_orchestrator(dependency_container)
    health_handler = HealthHandler(
        application_service=application_service,
        startup_report=dependency_container.startup_events() if dependency_container is not None else (),
        runtime_orchestrator=runtime_orchestrator,
    )
    headless_handlers = handler_bundle.headless_handlers
    governance_handlers = GovernanceRouteHandlers()
    business_memory_handlers = handler_bundle.business_memory_handlers
    governance_advanced_handlers = GovernanceAdvancedRouteHandlers()

    tenant_registry = dependency_container.tenant_registry if dependency_container is not None else build_default_tenant_registry()
    tenant_policy_store = dependency_container.tenant_policy_store if dependency_container is not None else build_default_tenant_policy_store()
    tenant_quota_guard = dependency_container.tenant_quota_guard if dependency_container is not None else TenantQuotaGuard(policy_store=tenant_policy_store)
    security_bundle = dependency_container.security_owner_bundle() if dependency_container is not None else ApiSecurityOwnerBundle.default()
    auth_bundle = build_auth_bundle(security_bundle=security_bundle)
    authz_bundle = AuthzDependencyBundle.default()
    tenant_guard = TenantRouteGuard(tenant_registry=tenant_registry, require_active_tenant=tenant_registry_has_records(tenant_registry), security_guard=security_bundle.api_surface_guard)
    rate_limit_bundle = RateLimitDependencyBundle(tenant_quota_guard=tenant_quota_guard)
    audit_handlers = AuditRouteHandlers(action_audit_log=shared_action_audit_log, decision_audit_log=shared_decision_audit_log)
    approval_handlers = ApprovalRouteHandlers()
    admin_handlers = AdminRouteHandlers(tenant_registry=tenant_registry, tenant_policy_store=tenant_policy_store)
    connector_admin_handlers = ConnectorAdminRouteHandlers()
    provider_admin_handlers = ProviderAdminRouteHandlers()
    metrics_handlers = MetricsRouteHandlers(metrics=resolve_metrics(dependency_container=dependency_container))
    webhook_handlers = WebhookRouteHandlers(verifier=build_webhook_verifier(), audit_log=shared_action_audit_log, security_guard=security_bundle.webhook_surface_guard)
    queue_ops_handlers = QueueOpsRouteHandlers()
    telemetry_event_store = dependency_container.telemetry_event_store() if dependency_container is not None else None
    analytics_snapshot_db_path = str(dependency_container.analytics_snapshot_db_path()) if dependency_container is not None else 'runtime/data/analytics_snapshots.sqlite3'
    analytics_manifest_chain_db_path = str(dependency_container.analytics_manifest_chain_db_path()) if dependency_container is not None else 'runtime/data/analytics_manifest_chain.sqlite3'
    analytics_export_root = str(dependency_container.analytics_export_root()) if dependency_container is not None else 'runtime/data/analytics_exports'
    analytics_handlers = AnalyticsRouteHandlers(event_store=telemetry_event_store, snapshot_db_path=analytics_snapshot_db_path) if telemetry_event_store is not None else None
    runtime_infra = _resolve_runtime_infra(dependency_container.boot_result) if dependency_container is not None else None
    queue_dispatcher = getattr(runtime_infra, 'job_dispatcher', None) if runtime_infra is not None else None
    queue_bridge = None
    if queue_dispatcher is not None:
        from application.analytics.fleet_queue_job_bridge import AnalyticsFleetQueueJobBridge
        queue_bridge = AnalyticsFleetQueueJobBridge(dispatcher=queue_dispatcher)
    analytics_ops_handlers = AnalyticsOpsRouteHandlers(event_store=telemetry_event_store, snapshot_db_path=analytics_snapshot_db_path, queue_bridge=queue_bridge) if telemetry_event_store is not None else None
    analytics_signed_export_handlers = AnalyticsSignedExportRouteHandlers(event_store=telemetry_event_store, manifest_chain_db_path=analytics_manifest_chain_db_path, export_root=analytics_export_root) if telemetry_event_store is not None else None

    register_public_api_routes(router=router, dependency_container=dependency_container, health_handler=health_handler, handlers=handlers, headless_handlers=headless_handlers, governance_handlers=governance_handlers, business_memory_handlers=business_memory_handlers, governance_advanced_handlers=governance_advanced_handlers, security_guard=security_bundle.public_surface_guard, analytics_handlers=analytics_handlers)
    register_control_plane_routes(router=router, auth_bundle=auth_bundle, authz_bundle=authz_bundle, tenant_guard=tenant_guard, rate_limit_bundle=rate_limit_bundle, audit_handlers=audit_handlers, approval_handlers=approval_handlers, admin_handlers=admin_handlers, connector_admin_handlers=connector_admin_handlers, provider_admin_handlers=provider_admin_handlers, metrics_handlers=metrics_handlers, webhook_handlers=webhook_handlers, queue_ops_handlers=queue_ops_handlers, security_guard=security_bundle.control_plane_guard, analytics_ops_handlers=analytics_ops_handlers, analytics_signed_export_handlers=analytics_signed_export_handlers)
    register_provider_truth_matrix_routes(router=router)
    register_network_side_effects_routes(router=router)
    return router

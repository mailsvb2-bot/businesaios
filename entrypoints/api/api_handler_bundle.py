from __future__ import annotations
CANON_API_HANDLER_BUNDLE_FINAL_OWNER = True


from dataclasses import dataclass

from entrypoints.api.business_memory_route_handlers import BusinessMemoryRouteHandlers, build_business_memory_route_handlers
from entrypoints.api.execute_action_port_provider import ExecuteActionPortProvider, build_execute_action_port_provider
from entrypoints.api.headless_route_handlers import HeadlessRouteHandlers, build_headless_route_handlers
from entrypoints.api.headless_runtime_provider import HeadlessRuntimeProvider, build_default_headless_runtime_provider
from entrypoints.api.route_handlers import RouteHandlers, build_route_handlers
from observability.action_audit_log import ActionAuditLog


CANON_API_HANDLER_BUNDLE_SINGLE_OWNER = True
CANON_API_HANDLER_BUNDLE_NO_DECISION_LOGIC = True


@dataclass(frozen=True)
class ApiHandlerBundle:
    route_handlers: RouteHandlers
    headless_handlers: HeadlessRouteHandlers
    business_memory_handlers: BusinessMemoryRouteHandlers
    execute_action_port_provider: ExecuteActionPortProvider | None = None



def build_api_handler_bundle(
    *,
    application_service: object,
    dependency_container: object | None = None,
    action_audit_log: ActionAuditLog | None = None,
    headless_runtime_provider: HeadlessRuntimeProvider | None = None,
    execute_action_port: object | None = None,
) -> ApiHandlerBundle:
    runtime_provider = headless_runtime_provider or build_default_headless_runtime_provider()
    execute_action_port_provider = build_execute_action_port_provider(
        application_service=application_service,
        dependency_container=dependency_container,
        action_audit_log=action_audit_log,
    )
    resolved_execute_action_port = execute_action_port if execute_action_port is not None else execute_action_port_provider.build_port()
    return ApiHandlerBundle(
        route_handlers=build_route_handlers(
            application_service=application_service,
            execute_action_port=resolved_execute_action_port,
        ),
        headless_handlers=build_headless_route_handlers(runtime_provider=runtime_provider),
        business_memory_handlers=build_business_memory_route_handlers(runtime_provider=runtime_provider),
        execute_action_port_provider=execute_action_port_provider,
    )


__all__ = [
    'CANON_API_HANDLER_BUNDLE_SINGLE_OWNER',
    'CANON_API_HANDLER_BUNDLE_NO_DECISION_LOGIC',
    'ApiHandlerBundle',
    'build_api_handler_bundle',
]

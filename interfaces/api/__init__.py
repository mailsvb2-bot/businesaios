"""Canonical interfaces.api package with package-owned compat aliases."""

from __future__ import annotations

import sys
from importlib import import_module
from types import ModuleType

CANON_INTERFACES_API_PACKAGE_OWNER = True
CANON_INTERFACES_API_PACKAGE_ALIAS_OWNER = True

_COMPAT_ALIAS_MAP = {
    "action_mapper": "entrypoints.api.action_mapper",
    "action_models": "entrypoints.api.action_models",
    "admin_route_handlers": "entrypoints.api.admin_route_handlers",
    "analytics_models": "entrypoints.api.analytics_models",
    "analytics_route_handlers": "entrypoints.api.analytics_route_handlers",
    "analytics_ops_route_handlers": "entrypoints.api.analytics_ops_route_handlers",
    "api_handler_bundle": "entrypoints.api.api_handler_bundle",
    "api_key_policy": "entrypoints.api.api_key_policy",
    "approval_route_handlers": "entrypoints.api.approval_route_handlers",
    "approval_route_support": "entrypoints.api.approval_route_support",
    "audit_route_handlers": "entrypoints.api.audit_route_handlers",
    "auth_contract": "entrypoints.api.auth_contract",
    "auth_dependencies": "adapters.api.fastapi.auth_dependencies",
    "authz_dependencies": "entrypoints.api.authz_dependencies",
    "baseline_models": "entrypoints.api.baseline_models",
    "baseline_route_handlers": "entrypoints.api.baseline_route_handlers",
    "business_memory_models": "entrypoints.api.business_memory_models",
    "connector_admin_route_handlers": "entrypoints.api.connector_admin_route_handlers",
    "webhook_security_surface_guard": "entrypoints.api.webhook_security_surface_guard",
    "control_plane_security_guard": "entrypoints.api.control_plane_security_guard",
    "drift_models": "entrypoints.api.drift_models",
    "drift_route_handlers": "entrypoints.api.drift_route_handlers",
    "error_mapper": "entrypoints.api.error_mapper",
    "error_models": "entrypoints.api.error_models",
    "error_presenter": "entrypoints.api.error_presenter",
    "execute_action_api_stack": "entrypoints.api.execute_action_api_stack",
    "execute_action_audit_payload": "entrypoints.api.execute_action_audit_payload",
    "execute_action_handler": "entrypoints.api.execute_action_handler",
    "execute_action_idempotency_store": "entrypoints.api.execute_action_idempotency_store",
    "execute_action_port_provider": "entrypoints.api.execute_action_port_provider",
    "execute_action_request_envelope": "entrypoints.api.execute_action_request_envelope",
    "execute_action_stack_bundle": "entrypoints.api.execute_action_stack_bundle",
    "execute_action_with_control_plane": "entrypoints.api.execute_action_with_control_plane",
    "execute_action_with_guards": "entrypoints.api.execute_action_with_guards",
    "fastapi_app_factory": "entrypoints.api.fastapi_app_factory",
    "fastapi_dependencies": "adapters.api.fastapi.dependencies",
    "fastapi_exception_handlers": "adapters.api.fastapi.exception_handlers",
    "fastapi_router_adapter": "adapters.api.fastapi.router_adapter",
    "fastapi_router_control_plane_routes": "adapters.api.fastapi.control_plane_routes",
    "fastapi_router_public_routes": "adapters.api.fastapi.public_routes",
    "fastapi_router_support": "adapters.api.fastapi.router_support",
    "governance_advanced_models": "entrypoints.api.governance_advanced_models",
    "governance_advanced_route_handlers": "entrypoints.api.governance_advanced_route_handlers",
    "governance_route_handlers": "entrypoints.api.governance_route_handlers",
    "headless_models": "entrypoints.api.headless_models",
    "headless_route_handlers": "entrypoints.api.headless_route_handlers",
    "headless_runtime_provider": "entrypoints.api.headless_runtime_provider",
    "health_handler": "entrypoints.api.health_handler",
    "health_models": "entrypoints.api.health_models",
    "jwt_policy": "entrypoints.api.jwt_policy",
    "metrics_route_handlers": "entrypoints.api.metrics_route_handlers",
    "openapi_security": "adapters.api.fastapi.openapi_security",
    "openapi_tags": "entrypoints.api.openapi_tags",
    "queue_ops_models": "entrypoints.api.queue_ops_models",
    "queue_ops_route_handlers": "entrypoints.api.queue_ops_route_handlers",
    "queue_ops_route_support": "entrypoints.api.queue_ops_route_support",
    "rate_limit_dependencies": "entrypoints.api.rate_limit_dependencies",
    "rbac_route_guards": "entrypoints.api.rbac_route_guards",
    "request_context": "entrypoints.api.request_context",
    "security_surface_guard": "entrypoints.api.security_surface_guard",
    "request_signing_policy": "entrypoints.api.request_signing_policy",
    "response_presenter": "entrypoints.api.response_presenter",
    "route_handlers": "entrypoints.api.route_handlers",
    "runtime_api_adapter": "adapters.api.runtime_api_adapter",
    "runtime_api_bundle": "entrypoints.api.runtime_api_bundle",
    "signature_binding": "entrypoints.api.signature_binding",
    "tenant_route_guards": "entrypoints.api.tenant_route_guards",
    "webhook_route_handlers": "entrypoints.api.webhook_route_handlers",
}

def _install_compat_aliases() -> None:
    package = sys.modules[__name__]

    def _build_alias_module(qualified_name: str, target_module_name: str) -> ModuleType:
        module = ModuleType(qualified_name)
        module.__file__ = f"<compat-alias {qualified_name}>"
        module.__package__ = __name__

        def _load_target() -> ModuleType:
            target = import_module(target_module_name)
            sys.modules[qualified_name] = target
            setattr(package, qualified_name.rsplit(".", 1)[-1], target)
            return target

        def __getattr__(name: str):
            return getattr(_load_target(), name)

        def __dir__():
            return sorted(set(dir(_load_target())))

        module.__getattr__ = __getattr__  # type: ignore[attr-defined]
        module.__dir__ = __dir__  # type: ignore[attr-defined]
        return module

    for alias_name, target_module_name in _COMPAT_ALIAS_MAP.items():
        qualified_name = f"{__name__}.{alias_name}"
        existing = sys.modules.get(qualified_name)
        if existing is None:
            existing = _build_alias_module(qualified_name, target_module_name)
            sys.modules[qualified_name] = existing
        setattr(package, alias_name, existing)

_install_compat_aliases()

__all__ = sorted(_COMPAT_ALIAS_MAP) + [
    'ApiSecurityOwnerBundle',
    'InferenceAdminRouteHandlers',
    'InferenceCapacityRouteHandlers',
    'InferenceProviderRouteHandlers',
    'InferenceRuntimeAdminRouteHandlers',
]


from entrypoints.api.security_owner_bundle import ApiSecurityOwnerBundle
from interfaces.api.inference_admin_route_handlers import InferenceAdminRouteHandlers
from interfaces.api.inference_capacity_route_handlers import InferenceCapacityRouteHandlers
from interfaces.api.inference_provider_route_handlers import InferenceProviderRouteHandlers
from interfaces.api.inference_runtime_admin_route_handlers import InferenceRuntimeAdminRouteHandlers

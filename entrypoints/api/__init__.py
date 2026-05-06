from __future__ import annotations

"""Lightweight canonical API entrypoint package surface.

The package root must stay import-safe: importing ``entrypoints.api`` must not
instantiate API handlers, FastAPI dependencies, provider runtimes, or control
plane modules. Public names are resolved lazily when explicitly requested.
"""

from importlib import import_module
from typing import Any

_CANONICAL_EXPORTS: dict[str, tuple[str, str]] = {
    "ApiAction": ("entrypoints.api.action_mapper", "ApiAction"),
    "map_execute_action_request": ("entrypoints.api.action_mapper", "map_execute_action_request"),
    "ApiHandlerBundle": ("entrypoints.api.api_handler_bundle", "ApiHandlerBundle"),
    "build_api_handler_bundle": ("entrypoints.api.api_handler_bundle", "build_api_handler_bundle"),
    "ExecuteActionHandler": ("entrypoints.api.execute_action_handler", "ExecuteActionHandler"),
    "build_execute_action_handler": ("entrypoints.api.execute_action_handler", "build_execute_action_handler"),
    "InferenceAdminRouteHandlers": ("entrypoints.api.inference_admin_route_handlers", "InferenceAdminRouteHandlers"),
    "InferenceCapacityRouteHandlers": ("entrypoints.api.inference_capacity_route_handlers", "InferenceCapacityRouteHandlers"),
    "InferenceProviderRouteHandlers": ("entrypoints.api.inference_provider_route_handlers", "InferenceProviderRouteHandlers"),
    "InferenceRuntimeAdminRouteHandlers": ("entrypoints.api.inference_runtime_admin_route_handlers", "InferenceRuntimeAdminRouteHandlers"),
}


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _CANONICAL_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_CANONICAL_EXPORTS))


__all__ = sorted(_CANONICAL_EXPORTS)

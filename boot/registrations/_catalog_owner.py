from __future__ import annotations

from typing import Final

from boot.registrations._shared import register_built_runtime_service
from boot.runtime_service_specs import (
    CATALOG_BACKED_RUNTIME_CALLABLES,
    CATALOG_BACKED_RUNTIME_SERVICES,
    get_runtime_service_spec,
    get_runtime_service_spec_by_callable,
)
from runtime.errors import RuntimeConfigurationError
from runtime.registry import RuntimeRegistry
from runtime.service_names import RuntimeServiceName


def _register_catalog_runtime_service(*, registry: RuntimeRegistry, service_name: str):
    spec = get_runtime_service_spec(service_name)
    from boot.factories import get_factory_for_service

    builder = get_factory_for_service(service_name)
    return register_built_runtime_service(
        registry,
        name=spec.service_name,
        builder=builder,
        service_type=spec.service_type,
        dependencies=spec.dependencies,
        dependency_map=spec.dependency_map,
    )


def register_architecture_watch(registry: RuntimeRegistry):
    return _register_catalog_runtime_service(
        registry=registry,
        service_name=RuntimeServiceName.ARCHITECTURE_WATCH,
    )


def register_autonomy_advisor(registry: RuntimeRegistry):
    return _register_catalog_runtime_service(
        registry=registry,
        service_name=RuntimeServiceName.AUTONOMY_ADVISOR,
    )


def register_creative_intelligence(registry: RuntimeRegistry):
    return _register_catalog_runtime_service(
        registry=registry,
        service_name=RuntimeServiceName.CREATIVE_INTELLIGENCE,
    )


def register_decision_gateway(registry: RuntimeRegistry):
    return _register_catalog_runtime_service(
        registry=registry,
        service_name=RuntimeServiceName.DECISION_GATEWAY,
    )


def register_decision_input_service(registry: RuntimeRegistry):
    return _register_catalog_runtime_service(
        registry=registry,
        service_name=RuntimeServiceName.DECISION_INPUT_SERVICE,
    )


def register_diffusion_watch(registry: RuntimeRegistry):
    return _register_catalog_runtime_service(
        registry=registry,
        service_name=RuntimeServiceName.DIFFUSION_WATCH,
    )


def register_flow_watch(registry: RuntimeRegistry):
    return _register_catalog_runtime_service(
        registry=registry,
        service_name=RuntimeServiceName.FLOW_WATCH,
    )


def register_market_watch(registry: RuntimeRegistry):
    return _register_catalog_runtime_service(
        registry=registry,
        service_name=RuntimeServiceName.MARKET_WATCH,
    )


def register_runtime_packet_provider(registry: RuntimeRegistry):
    return _register_catalog_runtime_service(
        registry=registry,
        service_name=RuntimeServiceName.RUNTIME_PACKET_PROVIDER,
    )


def register_runtime_state_enrichment(registry: RuntimeRegistry):
    return _register_catalog_runtime_service(
        registry=registry,
        service_name=RuntimeServiceName.RUNTIME_STATE_ENRICHMENT,
    )


def register_structure_watch(registry: RuntimeRegistry):
    return _register_catalog_runtime_service(
        registry=registry,
        service_name=RuntimeServiceName.STRUCTURE_WATCH,
    )


def register_world_state_integration(registry: RuntimeRegistry):
    return _register_catalog_runtime_service(
        registry=registry,
        service_name=RuntimeServiceName.WORLD_STATE_INTEGRATION,
    )


CATALOG_REGISTRATION_FUNCTION_NAMES: Final[tuple[str, ...]] = tuple(CATALOG_BACKED_RUNTIME_CALLABLES)
CATALOG_REGISTRATION_FUNCTIONS: Final[dict[str, object]] = {
    name: globals()[name]
    for name in CATALOG_REGISTRATION_FUNCTION_NAMES
}

_missing_wrappers = sorted(
    callable_name
    for callable_name in CATALOG_REGISTRATION_FUNCTION_NAMES
    if callable_name not in globals()
)
if _missing_wrappers:
    raise RuntimeConfigurationError(
        'Catalog registration drift: missing wrapper callables ' + ', '.join(_missing_wrappers)
    )

_wrapper_service_names = tuple(
    get_runtime_service_spec_by_callable(callable_name).service_name
    for callable_name in CATALOG_REGISTRATION_FUNCTION_NAMES
)
if tuple(sorted(_wrapper_service_names)) != tuple(sorted(CATALOG_BACKED_RUNTIME_SERVICES)):
    raise RuntimeConfigurationError(
        'Catalog registration drift between runtime service specs and registration wrappers.'
    )


__all__ = tuple(CATALOG_REGISTRATION_FUNCTION_NAMES) + (
    'CATALOG_REGISTRATION_FUNCTIONS',
    'CATALOG_REGISTRATION_FUNCTION_NAMES',
)

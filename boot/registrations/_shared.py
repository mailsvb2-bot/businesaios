from __future__ import annotations

from collections.abc import Callable, Mapping

from runtime.registration_result import RegistrationResult
from runtime.registry import RuntimeRegistry
from runtime.service_names import RuntimeServiceName
from runtime.service_types import RuntimeServiceType


def register_runtime_service(
    registry: RuntimeRegistry,
    *,
    name: RuntimeServiceName,
    service: object,
    service_type: RuntimeServiceType,
    dependencies: tuple[RuntimeServiceName, ...],
) -> RegistrationResult:
    registry.register(
        name=name,
        service=service,
        service_type=service_type,
        dependencies=dependencies,
    )
    return RegistrationResult(
        service_name=name,
        service_type=service_type,
        implementation_type=type(service).__name__,
        dependencies=dependencies,
    )


def resolve_registry_dependencies(
    registry: RuntimeRegistry,
    dependency_map: Mapping[str, RuntimeServiceName],
) -> dict[str, object]:
    return {
        argument_name: registry.get(service_name)
        for argument_name, service_name in dependency_map.items()
    }


def _validate_dependency_contract(
    *,
    dependencies: tuple[RuntimeServiceName, ...],
    dependency_map: Mapping[str, RuntimeServiceName] | None,
) -> None:
    if dependency_map is None:
        return
    declared = tuple(dependencies)
    mapped = tuple(dependency_map.values())
    if len(mapped) != len(set(mapped)):
        raise ValueError('dependency_map must not repeat runtime service names')
    extra_mapped = tuple(service_name for service_name in mapped if service_name not in declared)
    if extra_mapped:
        raise ValueError(
            'dependency_map must not reference undeclared runtime dependencies. '
            f'declared={declared!r} mapped={mapped!r}'
        )


def register_built_runtime_service(
    registry: RuntimeRegistry,
    *,
    name: RuntimeServiceName,
    builder: Callable[..., object],
    service_type: RuntimeServiceType,
    dependencies: tuple[RuntimeServiceName, ...],
    dependency_map: Mapping[str, RuntimeServiceName] | None = None,
) -> RegistrationResult:
    _validate_dependency_contract(
        dependencies=dependencies,
        dependency_map=dependency_map,
    )
    resolved_dependencies = resolve_registry_dependencies(
        registry,
        dependency_map or {},
    )
    service = builder(**resolved_dependencies)
    return register_runtime_service(
        registry,
        name=name,
        service=service,
        service_type=service_type,
        dependencies=dependencies,
    )


def register_runtime_singleton(
    registry: RuntimeRegistry,
    *,
    name: RuntimeServiceName,
    service_builder: Callable[[], object],
    service_type: RuntimeServiceType,
) -> RegistrationResult:
    return register_built_runtime_service(
        registry,
        name=name,
        builder=service_builder,
        service_type=service_type,
        dependencies=(),
    )


__all__ = [
    '_validate_dependency_contract',
    'register_built_runtime_service',
    'register_runtime_service',
    'register_runtime_singleton',
    'resolve_registry_dependencies',
]

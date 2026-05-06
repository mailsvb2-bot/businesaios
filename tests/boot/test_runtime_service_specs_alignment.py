from __future__ import annotations

from boot.factories import FACTORY_SERVICE_NAMES
from boot.registrations import CATALOG_REGISTRATION_FUNCTION_NAMES
from boot.runtime_service_specs import (
    CATALOG_BACKED_FACTORY_NAMES,
    CATALOG_BACKED_RUNTIME_CALLABLES,
    CATALOG_BACKED_RUNTIME_SERVICES,
    RUNTIME_BOOT_SERVICE_SPECS,
    SINGLETON_RUNTIME_CALLABLES,
    get_catalog_factory_name,
    get_runtime_service_spec_by_callable,
)


def test_factory_mapping_is_derived_from_runtime_service_specs() -> None:
    assert FACTORY_SERVICE_NAMES == CATALOG_BACKED_FACTORY_NAMES
    for service_name, factory_name in FACTORY_SERVICE_NAMES.items():
        assert get_catalog_factory_name(service_name) == factory_name


def test_catalog_registration_names_are_derived_from_runtime_service_specs() -> None:
    assert CATALOG_REGISTRATION_FUNCTION_NAMES == CATALOG_BACKED_RUNTIME_CALLABLES
    wrapper_services = tuple(
        get_runtime_service_spec_by_callable(callable_name).service_name
        for callable_name in CATALOG_REGISTRATION_FUNCTION_NAMES
    )
    assert tuple(sorted(wrapper_services)) == tuple(sorted(CATALOG_BACKED_RUNTIME_SERVICES))



def test_singleton_runtime_callables_cover_non_catalog_non_critical_wrappers() -> None:
    expected = tuple(
        spec.callable_name
        for spec in RUNTIME_BOOT_SERVICE_SPECS
        if spec.builder_name is None
        and spec.callable_name not in {"register_action_executor", "register_decision_core", "register_governance"}
    )
    assert SINGLETON_RUNTIME_CALLABLES == expected

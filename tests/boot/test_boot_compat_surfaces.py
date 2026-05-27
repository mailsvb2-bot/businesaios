from __future__ import annotations

import importlib

from boot.factories import FACTORY_COMPAT_EXPORTS, FACTORY_OWNER_MODULE
from boot.registrations import (
    CATALOG_OWNER_MODULE,
    REGISTRATION_CATALOG_COMPAT_EXPORTS,
    REGISTRATION_COMPAT_EXPORTS,
    SINGLETON_OWNER_MODULE,
)
from boot.runtime_service_specs import (
    CATALOG_BACKED_RUNTIME_CALLABLES,
    SINGLETON_RUNTIME_CALLABLES,
    build_registration_compat_exports,
)


def test_factory_compat_modules_resolve_to_canonical_owner_exports() -> None:
    owner = importlib.import_module(FACTORY_OWNER_MODULE)
    for export_name, module_name in FACTORY_COMPAT_EXPORTS.items():
        compat = importlib.import_module(f'boot.factories.{module_name}')
        assert getattr(compat, export_name) is getattr(owner, export_name)


def test_registration_compat_modules_resolve_to_canonical_owner_exports() -> None:
    singleton_owner = importlib.import_module(SINGLETON_OWNER_MODULE)
    for export_name, module_name in REGISTRATION_COMPAT_EXPORTS.items():
        compat = importlib.import_module(f'boot.registrations.{module_name}')
        assert getattr(compat, export_name) is getattr(singleton_owner, export_name)

    catalog_owner = importlib.import_module(CATALOG_OWNER_MODULE)
    for export_name, module_name in REGISTRATION_CATALOG_COMPAT_EXPORTS.items():
        compat = importlib.import_module(f'boot.registrations.{module_name}')
        assert getattr(compat, export_name) is getattr(catalog_owner, export_name)



def test_registration_compat_exports_are_derived_from_runtime_service_specs() -> None:
    assert REGISTRATION_COMPAT_EXPORTS == build_registration_compat_exports(
        callable_names=SINGLETON_RUNTIME_CALLABLES,
    )
    assert REGISTRATION_CATALOG_COMPAT_EXPORTS == build_registration_compat_exports(
        callable_names=CATALOG_BACKED_RUNTIME_CALLABLES,
    )

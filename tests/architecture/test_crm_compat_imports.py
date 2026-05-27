from __future__ import annotations

import importlib

import pytest

PROJECT_BOUNDARY_MODULES = (
    "execution.evidence.base",
    "execution.evidence.result",
    "interfaces.common.registry_capability_contract",
)

MODULES = (
    "execution.evidence.crm",
    "interfaces.crm",
    "interfaces.crm.hubspot_connector",
    "interfaces.crm.registry",
    "runtime.bootstrap",
    "runtime.bootstrap.crm_bootstrap",
    "runtime.bootstrap.crm_registry_boot",
)



def test_compatibility_modules_import_when_project_surfaces_exist() -> None:
    for dependency in PROJECT_BOUNDARY_MODULES:
        try:
            importlib.import_module(dependency)
        except ModuleNotFoundError:
            pytest.skip("project compatibility surfaces are not present in patch-only archive")

    for module_name in MODULES:
        importlib.import_module(module_name)

from __future__ import annotations

import sys
import types

import pytest

from runtime.public_api_alias import install_public_api_alias


def test_public_api_alias_rejects_existing_foreign_nested_alias() -> None:
    module_name = "tests.fake_public_api_alias_pkg"
    alias_name = f"{module_name}.public_api"
    nested_alias_name = f"{alias_name}.public_api"
    module = types.ModuleType(module_name)
    alias_module = types.ModuleType(alias_name)
    foreign = types.ModuleType(nested_alias_name)
    sys.modules[module_name] = module
    sys.modules[alias_name] = alias_module
    sys.modules[nested_alias_name] = foreign
    try:
        with pytest.raises(RuntimeError, match="public api alias collision"):
            install_public_api_alias(module_name)
    finally:
        sys.modules.pop(module_name, None)
        sys.modules.pop(alias_name, None)
        sys.modules.pop(nested_alias_name, None)



def test_public_api_alias_rejects_existing_foreign_attribute() -> None:
    module_name = "tests.fake_public_api_attr_pkg"
    alias_name = f"{module_name}.public_api"
    module = types.ModuleType(module_name)
    alias_module = types.ModuleType(alias_name)
    alias_module.public_api = object()
    sys.modules[module_name] = module
    sys.modules[alias_name] = alias_module
    try:
        with pytest.raises(RuntimeError, match="public api attribute collision"):
            install_public_api_alias(module_name)
    finally:
        sys.modules.pop(module_name, None)
        sys.modules.pop(alias_name, None)
        sys.modules.pop(f"{alias_name}.public_api", None)

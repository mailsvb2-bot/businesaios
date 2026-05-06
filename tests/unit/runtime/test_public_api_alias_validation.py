from __future__ import annotations

import types

import pytest

from runtime.public_api_alias import install_public_api_alias


@pytest.mark.parametrize("module_name", ["", "bad-name", "runtime.bad-name", "a..b"])
def test_install_public_api_alias_rejects_invalid_names(module_name: str) -> None:
    with pytest.raises(RuntimeError):
        install_public_api_alias(module_name)



def test_install_public_api_alias_keeps_existing_package_alias() -> None:
    package = types.ModuleType("runtime_test_pkg")
    public_api = types.ModuleType("runtime_test_pkg.public_api")

    import sys

    sys.modules[package.__name__] = package
    sys.modules[public_api.__name__] = public_api
    try:
        install_public_api_alias(package.__name__)
        assert sys.modules["runtime_test_pkg.public_api.public_api"] is public_api
        assert public_api.public_api is public_api
    finally:
        sys.modules.pop("runtime_test_pkg.public_api.public_api", None)
        sys.modules.pop(public_api.__name__, None)
        sys.modules.pop(package.__name__, None)

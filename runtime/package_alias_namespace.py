from __future__ import annotations

import importlib
import sys
from collections.abc import Iterable, Mapping
from typing import Any

from runtime.public_api_alias import install_public_api_alias

CANON_RUNTIME_PACKAGE_ALIAS_HELPER = True


def build_package_alias_namespace(
    module_name: str,
    public_attrs: Mapping[str, tuple[str, str]],
    *,
    extra_exports: Iterable[str] = (),
    compat_alias_map: Mapping[str, str] | None = None,
    install_public_api: bool = True,
) -> tuple[object, object, list[str]]:
    if install_public_api:
        install_public_api_alias(module_name)

    package = sys.modules[module_name]
    if compat_alias_map:
        for alias_name, target in compat_alias_map.items():
            target_module = importlib.import_module(target)
            qualified_name = f"{module_name}.{alias_name}"
            sys.modules[qualified_name] = target_module
            setattr(package, alias_name, target_module)

    def __getattr__(name: str) -> Any:
        target = public_attrs.get(name)
        if target is None:
            raise AttributeError(name)
        target_module_name, attr_name = target
        if target_module_name == module_name:
            return getattr(package, attr_name)
        target_module = importlib.import_module(target_module_name)
        value = getattr(target_module, attr_name)
        setattr(package, name, value)
        return value

    def __dir__() -> list[str]:
        return sorted(set(package.__dict__) | set(public_attrs) | set(extra_exports))

    exports = sorted(set(public_attrs) | set(extra_exports))
    return __getattr__, __dir__, exports


__all__ = ["CANON_RUNTIME_PACKAGE_ALIAS_HELPER", "build_package_alias_namespace"]

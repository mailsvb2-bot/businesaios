from __future__ import annotations

import importlib
import sys
from collections.abc import Iterable, Mapping
from typing import Any

from runtime.public_api_alias import install_public_api_alias

CANON_RUNTIME_LAZY_NAMESPACE = True


def build_owner_namespace(
    module_name: str,
    owner_module_name: str,
    *,
    exports: Iterable[str] | None = None,
    install_public_api: bool = False,
) -> tuple[object, object, list[str]]:
    package = sys.modules[module_name]
    owner_module = importlib.import_module(owner_module_name)

    if install_public_api:
        install_public_api_alias(module_name)
    owner_exports = list(exports if exports is not None else getattr(owner_module, "__all__", ()))

    def __getattr__(name: str) -> Any:
        if name not in owner_exports:
            raise AttributeError(name)
        value = getattr(owner_module, name)
        setattr(package, name, value)
        return value

    def __dir__() -> list[str]:
        return sorted(set(package.__dict__) | set(owner_exports))

    return __getattr__, __dir__, owner_exports


def install_module_aliases(
    package_name: str,
    aliases: Mapping[str, str] | Iterable[str],
) -> None:
    package = sys.modules[package_name]
    if isinstance(aliases, Mapping):
        alias_items = aliases.items()
    else:
        alias_items = ((alias_name, package_name) for alias_name in aliases)
    for alias_name, target in alias_items:
        target_module = importlib.import_module(target)
        qualified_name = f"{package_name}.{alias_name}"
        sys.modules[qualified_name] = target_module
        setattr(package, alias_name, target_module)


__all__ = [
    "CANON_RUNTIME_LAZY_NAMESPACE",
    "build_owner_namespace",
    "install_module_aliases",
]

"""Runtime platform config package surface.

Keep root import light. Heavy settings/YAML helpers are loaded only when the
caller asks for them, while the historical yaml_loader alias remains available.
"""

from __future__ import annotations


import sys
from importlib import import_module
from typing import Any

CANON_TRANSITION_SURFACE = True
CANON_COMPAT_SHIM = True
CANON_RUNTIME_PLATFORM_CONFIG_ALIAS_OWNER = True

_CANONICAL_EXPORTS: dict[str, tuple[str, str]] = {
    "load_settings": ("runtime.platform.config.settings_loader", "load_settings"),
    "FeatureFlags": ("runtime.platform.config.feature_flags", "FeatureFlags"),
    "YamlLoadResult": ("config.yaml_loader_shared", "YamlLoadResult"),
    "load_yaml": ("config.yaml_loader_shared", "load_yaml"),
    "load_yaml_optional": ("config.yaml_loader_shared", "load_yaml_optional"),
}


def _install_config_aliases() -> None:
    package = sys.modules[__name__]
    target_module = import_module("config.yaml_loader_shared")
    qualified_name = f"{__name__}.yaml_loader"
    sys.modules.setdefault(qualified_name, target_module)
    setattr(package, "yaml_loader", target_module)


def __getattr__(name: str) -> Any:
    if name == "yaml_loader":
        _install_config_aliases()
        return sys.modules[f"{__name__}.yaml_loader"]
    try:
        module_name, attr_name = _CANONICAL_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_CANONICAL_EXPORTS) | {"yaml_loader"})


__all__ = [
    "CANON_TRANSITION_SURFACE",
    "CANON_COMPAT_SHIM",
    "CANON_RUNTIME_PLATFORM_CONFIG_ALIAS_OWNER",
    "load_settings",
    "FeatureFlags",
    "load_yaml",
    "load_yaml_optional",
    "YamlLoadResult",
]

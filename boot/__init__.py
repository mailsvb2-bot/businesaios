from __future__ import annotations

import importlib

CANON_BOOT_PACKAGE_API = True
CANON_LEGACY_BOOTSTRAP_PACKAGE_SHIM = True
CANON_BOOT_PACKAGE_OWNER = True
CANON_BOOT_PACKAGE_LAZY_EXPORTS = True
CANON_BOOT_PACKAGE_DIRECT_OWNER_EXPORTS = True
CANON_BOOT_PUBLIC_API = True
CANON_LEGACY_BOOTSTRAP_SHIM = True
CANON_BOOT_PUBLIC_API_COMPAT_SHELL = True
CANON_BOOT_PUBLIC_API_DIRECT_OWNER_DELEGATION = True
CANON_BOOT_PUBLIC_API_DIRECT_RUNTIME_TYPE_EXPORT = True
CANON_BOOT_PACKAGE_DIRECT_BOOTSTRAP_COMPOSE_RUNTIME = True
CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API = "bootstrap.compose"
CANON_BOOT_PACKAGE_ALIAS_OWNER = True

_COMPAT_ALIAS_MAP = {
    "app_boot_contracts": "bootstrap.app_boot_contracts",
    "app_boot_guard": "bootstrap.app_boot_guard",
    "app_boot_observability": "bootstrap.app_boot_observability",
    "app_boot_result": "bootstrap.app_boot_result",
    "bootstrap_config_surface": "bootstrap.bootstrap_config_surface",
    "platform_boot_contract": "bootstrap.platform_boot_contract",
    "platform_boot_surface": "bootstrap.platform_boot_surface",
    "runtime_boot": "bootstrap.runtime_boot",
    "runtime_boot_guard": "bootstrap.runtime_boot_guard",
    "runtime_boot_manifest": "bootstrap.runtime_boot_manifest",
    "runtime_boot_report": "bootstrap.runtime_boot_report",
    "runtime_dependency_sets": "bootstrap.runtime_dependency_sets",
    "runtime_manifest_support": "bootstrap.runtime_manifest_support",
    "runtime_service_specs": "bootstrap.runtime_service_specs",
    "startup_pipeline": "bootstrap.startup_pipeline",
    "system_boot_surface": "bootstrap.system_boot_surface",
    "system_registry_boot": "bootstrap.system_registry_boot",
}

_EXPORT_MAP = {
    "BuiltRuntime": ("runtime.bootstrap", "BuiltRuntime"),
    "build_runtime": ("bootstrap.compose", "build_runtime"),
    "bootstrap_runtime": ("runtime.bootstrap.sovereign_bootstrap", "bootstrap_runtime"),
    "get_bootstrapped_runtime": ("runtime.bootstrap.sovereign_bootstrap", "get_bootstrapped_runtime"),
    "BootFacade": ("boot.facade", "BootFacade"),
    "build_app_boot_surface": ("bootstrap.app_boot_surface", "build_app_boot_surface"),
    "build_http_boot_surface": ("bootstrap.http_boot_surface", "build_http_boot_surface"),
    "boot_application": ("bootstrap.app_boot", "boot_application"),
    "boot_http_app": ("bootstrap.http_boot_surface", "build_http_boot_surface"),
    "get_boot_facade": ("boot.facade", "get_boot_facade"),
}

__all__ = [
    "CANON_BOOT_PACKAGE_API",
    "CANON_LEGACY_BOOTSTRAP_PACKAGE_SHIM",
    "CANON_BOOT_PACKAGE_OWNER",
    "CANON_BOOT_PACKAGE_LAZY_EXPORTS",
    "CANON_BOOT_PACKAGE_DIRECT_OWNER_EXPORTS",
    "CANON_BOOT_PUBLIC_API",
    "CANON_LEGACY_BOOTSTRAP_SHIM",
    "CANON_BOOT_PUBLIC_API_COMPAT_SHELL",
    "CANON_BOOT_PUBLIC_API_DIRECT_OWNER_DELEGATION",
    "CANON_BOOT_PUBLIC_API_DIRECT_RUNTIME_TYPE_EXPORT",
    "CANON_BOOT_PACKAGE_DIRECT_BOOTSTRAP_COMPOSE_RUNTIME",
    "CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API",
    "build_runtime",
    "bootstrap_runtime",
    "boot_application",
    "boot_http_app",
    *tuple(_EXPORT_MAP.keys()),
]


def _load_attr(module_name: str, attr_name: str):
    return getattr(importlib.import_module(module_name), attr_name)


def bootstrap_runtime(*args, **kwargs):
    return _load_attr("runtime.bootstrap.sovereign_bootstrap", "bootstrap_runtime")(*args, **kwargs)


def build_runtime(*args, **kwargs):
    return _load_attr("bootstrap.compose", "build_runtime")(*args, **kwargs)


def boot_application(*args, **kwargs):
    return _load_attr("bootstrap.app_boot", "boot_application")(*args, **kwargs)


def boot_http_app(*args, **kwargs):
    return _load_attr("bootstrap.http_boot_surface", "build_http_boot_surface")(*args, **kwargs).http_app


def __getattr__(name: str):
    if name in {
        "CANON_BOOT_PACKAGE_API",
        "CANON_LEGACY_BOOTSTRAP_PACKAGE_SHIM",
        "CANON_BOOT_PACKAGE_OWNER",
        "CANON_BOOT_PACKAGE_LAZY_EXPORTS",
        "CANON_BOOT_PACKAGE_DIRECT_OWNER_EXPORTS",
        "CANON_BOOT_PUBLIC_API",
        "CANON_LEGACY_BOOTSTRAP_SHIM",
        "CANON_BOOT_PUBLIC_API_COMPAT_SHELL",
        "CANON_BOOT_PUBLIC_API_DIRECT_OWNER_DELEGATION",
        "CANON_BOOT_PUBLIC_API_DIRECT_RUNTIME_TYPE_EXPORT",
        "CANON_BOOT_PACKAGE_DIRECT_BOOTSTRAP_COMPOSE_RUNTIME",
        "CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API",
        "build_runtime",
        "bootstrap_runtime",
        "boot_application",
        "boot_http_app",
    }:
        return globals()[name]
    target = _EXPORT_MAP.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attr_name = target
    loaded = _load_attr(module_name, attr_name)
    globals()[name] = loaded
    return loaded


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))


def _install_compat_aliases() -> None:
    sys_module = importlib.import_module("sys")
    module_type = importlib.import_module("types").ModuleType
    package = sys_module.modules[__name__]

    def _build_alias_module(qualified_name: str, target_module_name: str):
        module = module_type(qualified_name)
        module.__file__ = f"<compat-alias {qualified_name}>"
        module.__package__ = __name__

        def _load_target():
            target = importlib.import_module(target_module_name)
            sys_module.modules[qualified_name] = target
            object.__setattr__(package, qualified_name.rsplit(".", 1)[-1], target)
            return target

        def __getattr__(name: str):
            return getattr(_load_target(), name)

        def __dir__():
            return sorted(set(dir(_load_target())))

        module.__getattr__ = __getattr__  # type: ignore[attr-defined]
        module.__dir__ = __dir__  # type: ignore[attr-defined]
        return module

    for alias_name, target_module_name in _COMPAT_ALIAS_MAP.items():
        qualified_name = f"{__name__}.{alias_name}"
        existing = sys_module.modules.get(qualified_name)
        if existing is None:
            existing = _build_alias_module(qualified_name, target_module_name)
            sys_module.modules[qualified_name] = existing
        object.__setattr__(package, alias_name, existing)


_install_compat_aliases()
importlib.import_module("canon.public_api_alias").install_public_api_alias(__name__)

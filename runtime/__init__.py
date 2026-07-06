"""Package marker for BUSINESAIOS canonical runtime namespace.

This root must stay import-light. It intentionally avoids eager compat-target imports
so foundational modules such as runtime.service_names can be imported without pulling
in runtime.application and triggering circular initialization.
"""

from __future__ import annotations

import sys
from importlib import import_module
from types import ModuleType

from shared.registry import ComponentRegistry, ServiceRegistry

CANON_RUNTIME_NAMESPACE = True
CANON_COMPAT_SHIM = True
__all__ = ["CANON_RUNTIME_NAMESPACE", "CANON_COMPAT_SHIM", "CANON_RUNTIME_PACKAGE_ALIAS_OWNER", "ServiceRegistry", "ComponentRegistry"]
CANON_RUNTIME_PACKAGE_ALIAS_OWNER = True
_COMPAT_ALIAS_MAP = {
    "bootstrap_process": "bootstrap.process_hygiene",
    "bootstrap_prod_guards": "bootstrap.prod_guards",
    "executor_effects": "runtime.execution.executor_state",
    "executor_infra": "runtime.execution.executor_state",
    "executor_ports": "runtime.execution.executor_state",
    "llm_provider_factory": "runtime.llm",
}

def _install_runtime_compat_aliases() -> None:
    package = sys.modules[__name__]

    def _build_alias_module(qualified_name: str, target_module_name: str) -> ModuleType:
        module = ModuleType(qualified_name)
        module.__file__ = f"<compat-alias {qualified_name}>"
        module.__package__ = __name__

        def _load_target() -> ModuleType:
            target = import_module(target_module_name)
            sys.modules[qualified_name] = target
            setattr(package, qualified_name.rsplit(".", 1)[-1], target)
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
        existing = sys.modules.get(qualified_name)
        if existing is None:
            existing = _build_alias_module(qualified_name, target_module_name)
            sys.modules[qualified_name] = existing
        setattr(package, alias_name, existing)


_install_runtime_compat_aliases()

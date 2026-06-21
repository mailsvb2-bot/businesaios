from __future__ import annotations

import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from types import ModuleType
from typing import Any

CANON_OWNER_MODULE_INSTALLER = True


def install_owner_submodules(
    package_name: str,
    module_exports: Mapping[str, str],
    *,
    owner_getter: Callable[[], Any],
) -> None:
    package = sys.modules.get(package_name)
    if not isinstance(package, ModuleType):
        return
    package_file = Path(str(getattr(package, "__file__", f"{package_name.replace('.', '/')}/__init__.py")))
    for module_name, export_name in module_exports.items():
        qualified_name = f"{package_name}.{module_name}"
        value = getattr(owner_getter(), export_name)
        module = ModuleType(qualified_name)
        module.__dict__.update(
            {
                export_name: value,
                "__all__": [export_name],
                "__file__": str(package_file.with_name(f"{module_name}.py")),
                "__package__": package_name,
                "__doc__": f"Owner module door for {qualified_name}",
            }
        )
        sys.modules[qualified_name] = module
        setattr(package, module_name, module)


__all__ = ["CANON_OWNER_MODULE_INSTALLER", "install_owner_submodules"]

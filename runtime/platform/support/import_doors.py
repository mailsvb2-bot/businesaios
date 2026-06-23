from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import json
import sys
from pathlib import Path
from types import ModuleType

CANON_RUNTIME_PLATFORM_SUPPORT_IMPORT_DOORS = True


def _load_runtime_platform_support_import_doors() -> dict[str, dict[str, str]]:
    registry_path = Path(__file__).with_name("import_doors_registry.json")
    with registry_path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return {
        str(module_name): {str(export_name): str(target_module) for export_name, target_module in exports.items()}
        for module_name, exports in raw.items()
    }


RUNTIME_PLATFORM_SUPPORT_IMPORT_DOORS = _load_runtime_platform_support_import_doors()


class _RuntimePlatformSupportDoorFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname: str, path=None, target=None):
        if fullname not in RUNTIME_PLATFORM_SUPPORT_IMPORT_DOORS:
            return None
        return importlib.machinery.ModuleSpec(fullname, self)

    def create_module(self, spec):
        return ModuleType(spec.name)

    def exec_module(self, module) -> None:
        exports = RUNTIME_PLATFORM_SUPPORT_IMPORT_DOORS[module.__name__]
        module.__all__ = list(exports)
        module.__package__ = module.__name__.rpartition(".")[0]
        module.__file__ = module.__name__.replace(".", "/") + ".py"
        for name, target_spec in exports.items():
            target_module, separator, target_attr = str(target_spec).partition(":")
            owner = importlib.import_module(target_module)
            setattr(module, name, getattr(owner, target_attr or name))


_FINDER = _RuntimePlatformSupportDoorFinder()


def install_runtime_platform_support_import_doors() -> None:
    if not any(finder is _FINDER for finder in sys.meta_path):
        sys.meta_path.insert(0, _FINDER)


__all__ = [
    "CANON_RUNTIME_PLATFORM_SUPPORT_IMPORT_DOORS",
    "RUNTIME_PLATFORM_SUPPORT_IMPORT_DOORS",
    "install_runtime_platform_support_import_doors",
]

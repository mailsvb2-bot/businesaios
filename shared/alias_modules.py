from __future__ import annotations

from importlib import import_module
from types import ModuleType
from typing import Mapping
import sys


def _ensure_alias_module(*, package_name: str, module_name: str, doc_suffix: str) -> ModuleType:
    qualified_name = f"{package_name}.{module_name}"
    module = sys.modules.get(qualified_name)
    if module is None:
        module = ModuleType(qualified_name)
        module.__package__ = package_name
        module.__file__ = f"<compat:{qualified_name}>"
        module.__doc__ = doc_suffix
        sys.modules[qualified_name] = module
    return module


def install_alias_modules(package_name: str, module_exports: Mapping[str, Mapping[str, str]]) -> None:
    """Install lightweight transition alias submodules for stable historical import paths."""
    package = sys.modules[package_name]
    for module_name, exports in module_exports.items():
        module = _ensure_alias_module(
            package_name=package_name,
            module_name=module_name,
            doc_suffix=(
                f"Transition alias module for {package_name}.{module_name}. "
                "The canonical implementation lives in the referenced catalog."
            ),
        )
        names: list[str] = []
        for export_name, import_path in exports.items():
            source_module_name, attribute_name = import_path.rsplit(":", 1)
            source_module = import_module(source_module_name)
            setattr(module, export_name, getattr(source_module, attribute_name))
            names.append(export_name)
        module.__all__ = list(names)
        setattr(package, module_name, module)


def register_alias_modules(*, package_name: str, source_module: str, aliases: Mapping[str, str]) -> None:
    """Register thin transition alias submodules that re-export symbols from one source module.

    This keeps old import paths stable while collapsing fleets of one-class wrapper files.
    """
    source = import_module(source_module)
    package = sys.modules[package_name]
    for module_basename, symbol_name in aliases.items():
        module = _ensure_alias_module(
            package_name=package_name,
            module_name=module_basename,
            doc_suffix=f"Compat alias for {source_module}.{symbol_name}.",
        )
        symbol = getattr(source, symbol_name)
        qualified_name = module.__name__
        module.__dict__.clear()
        module.__dict__.update(
            {
                '__name__': qualified_name,
                '__package__': package_name,
                '__file__': f"<compat:{package_name}.{module_basename}>",
                '__doc__': f"Compat alias for {source_module}.{symbol_name}.",
                symbol_name: symbol,
                '__all__': [symbol_name],
            }
        )
        setattr(package, module_basename, module)

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _validate_declared_file_path(file_path) -> None:
    if file_path is None:
        return
    resolved = Path(file_path).resolve()
    try:
        resolved.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise RuntimeError(f'outside project root: {resolved}') from exc


def import_attr(module_name: str, attr_name: str) -> Any:
    """Load an attribute through the canonical runtime loader surface.

    This is the single approved dynamic import helper for runtime/bootstrap
    wiring that still needs late binding. It keeps dynamic imports out of
    business/runtime modules so architecture-bypass scanning can enforce one
    explicit loader owner instead of scattered ``__import__`` calls.
    """

    module = importlib.import_module(str(module_name))
    return getattr(module, str(attr_name))


def import_internal_attr(module_name: str, attr_name: str) -> Any:
    """Load runtime._internal attributes under the explicit import-guard token."""

    from runtime.firewall.import_guard import ALLOW_INTERNAL_IMPORT

    token = ALLOW_INTERNAL_IMPORT.set(True)
    try:
        return import_attr(module_name, attr_name)
    finally:
        ALLOW_INTERNAL_IMPORT.reset(token)


def import_module_or_file(*, module_name: str, file_path, fallback_name: str) -> ModuleType:
    """Compatibility shim for historical callers.

    The canonical runtime.handlers surface is now a real package, so callers must import
    the declared module path directly. ``file_path`` is kept only as a safety contract to
    reject legacy outside-project fallback targets.
    """

    _validate_declared_file_path(file_path)
    del fallback_name
    return importlib.import_module(module_name)

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _validate_declared_file_path(file_path) -> None:
    if file_path is None:
        return
    resolved = Path(file_path).resolve()
    try:
        resolved.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise RuntimeError(f'outside project root: {resolved}') from exc


def import_module_or_file(*, module_name: str, file_path, fallback_name: str) -> ModuleType:
    """Compatibility shim for historical callers.

    The canonical runtime.handlers surface is now a real package, so callers must import
    the declared module path directly. ``file_path`` is kept only as a safety contract to
    reject legacy outside-project fallback targets.
    """

    _validate_declared_file_path(file_path)
    del fallback_name
    return importlib.import_module(module_name)

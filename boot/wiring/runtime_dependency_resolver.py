from __future__ import annotations

from importlib import import_module
from typing import Callable

from runtime.errors import RuntimeConfigurationError


class RuntimeDependencyResolver:
    def resolve_callable(self, module_path: str, callable_name: str) -> Callable:
        try:
            module = import_module(module_path)
        except (ImportError, SyntaxError, ValueError) as exc:
            raise RuntimeConfigurationError(
                f"Failed to import runtime registration module '{module_path}'."
            ) from exc

        try:
            target = getattr(module, callable_name)
        except AttributeError as exc:
            raise RuntimeConfigurationError(
                f"Callable '{callable_name}' not found in '{module_path}'."
            ) from exc

        if not callable(target):
            raise RuntimeConfigurationError(
                f"Resolved object '{module_path}:{callable_name}' is not callable."
            )

        return target

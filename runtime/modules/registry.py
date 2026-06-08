from __future__ import annotations

from collections.abc import Iterable

from runtime.modules.module_protocol import RuntimeModule

CANON_RUNTIME_MODULE_REGISTRY_OWNER = True


class ModuleRegistry:
    """Canonical mapping module_id -> module implementation."""

    def __init__(self, modules: Iterable[RuntimeModule]) -> None:
        self._by_id: dict[str, RuntimeModule] = {}
        for module in modules:
            module_id = getattr(module, "module_id", None)
            if not module_id:
                raise ValueError(f"Module missing module_id: {module}")
            if module_id in self._by_id:
                raise ValueError(f"Duplicate module_id: {module_id}")
            self._by_id[module_id] = module

    def get(self, module_id: str) -> RuntimeModule:
        try:
            return self._by_id[module_id]
        except KeyError as exc:
            raise KeyError(f"Unknown module_id: {module_id}") from exc

    def list_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_id.keys()))



def build_runtime_module_registry(modules: Iterable[RuntimeModule]) -> ModuleRegistry:
    return ModuleRegistry(modules)


__all__ = [
    "CANON_RUNTIME_MODULE_REGISTRY_OWNER",
    "ModuleRegistry",
    "build_runtime_module_registry",
]

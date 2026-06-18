from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True
CANON_PRODUCT_SYSTEM_WIRING_ADAPTER_OWNER = True
CANON_RUNTIME_BOOT_PRODUCT_SYSTEM_PIPELINE_ALIAS = True

"""Runtime boot alias for the product-contract wiring adapter owner.

The implementation remains in ``bootstrap.product_system_builder_pipeline``;
this module preserves the runtime/boot owner surface expected by architecture
locks without creating a second product-system pipeline.
"""

from bootstrap.product_system_builder_pipeline import (  # noqa: F401
    EnforcerAdapter,
    SelectorAdapter,
    WiringAdapter,
    build_product_system_wiring_adapter,
)
from bootstrap.product_system_builder_pipeline import _wire_default_builtin_modules as _owner_wire_default_builtin_modules
from runtime.modules.builtin_modules import DEFAULT_RUNTIME_MODULE_IDS
from runtime.modules.module_protocol import ModuleWiringContext
from runtime.modules.registry import ModuleRegistry
from bootstrap.product_system_builder_contracts import RuntimeView


def wire_default_builtin_modules(*, modules: ModuleRegistry, view: RuntimeView, wiring: ModuleWiringContext) -> None:
    for module_id in DEFAULT_RUNTIME_MODULE_IDS:
        _ = module_id
    _owner_wire_default_builtin_modules(modules=modules, view=view, wiring=wiring)


__all__ = [
    "CANON_PRODUCT_SYSTEM_WIRING_ADAPTER_OWNER",
    "EnforcerAdapter",
    "SelectorAdapter",
    "WiringAdapter",
    "build_product_system_wiring_adapter",
    "wire_default_builtin_modules",
]

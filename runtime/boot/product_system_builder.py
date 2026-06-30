"""Runtime boot alias for the product-contract system builder.

The implementation remains in ``bootstrap.product_system_builder``. This module
keeps the runtime/boot owner surface stable while delegating to the single
canonical product-contract builder.
"""

from __future__ import annotations

from bootstrap.product_system_builder import ProductContractSystem, SystemBuilder
from runtime.boot.product_system_builder_pipeline import build_product_system_wiring_adapter
from runtime.modules.builtin_modules import build_builtin_runtime_modules
from runtime.modules.registry import build_runtime_module_registry

CANON_BOOT_WIRING_ONLY = True
CANON_RUNTIME_BOOT_PRODUCT_SYSTEM_BUILDER_ALIAS = True
__all__ = [
    "ProductContractSystem",
    "SystemBuilder",
    "build_builtin_runtime_modules",
    "build_product_system_wiring_adapter",
    "build_runtime_module_registry",
]


from __future__ import annotations

"""Lightweight compatibility surface for historical runtime assembly imports.

Canonical boot assembly owner: :mod:`runtime.boot.boot_core_assembly`.
This adapter binds public names explicitly so static quality gates can verify the
surface while preserving a single canonical implementation owner.
"""

from runtime.boot.boot_core_assembly import (
    CANON_BOOT_WIRING_ONLY,
    CoreAssembly,
    build_core_assembly,
    build_decision_core,
    build_reward_and_learning_components,
    build_survival_and_economics,
)

CANON_RUNTIME_BOOT_ASSEMBLY_THIN_ADAPTER = True
CANON_RUNTIME_BOOT_ASSEMBLY_IMPORT_LIGHTWEIGHT = True

__all__ = [
    "CANON_RUNTIME_BOOT_ASSEMBLY_THIN_ADAPTER",
    "CANON_RUNTIME_BOOT_ASSEMBLY_IMPORT_LIGHTWEIGHT",
    "CANON_BOOT_WIRING_ONLY",
    "CoreAssembly",
    "build_core_assembly",
    "build_decision_core",
    "build_reward_and_learning_components",
    "build_survival_and_economics",
]

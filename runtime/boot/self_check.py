"""Boot-time self-check helpers for canonical decision surfaces.

This module is wiring-only and validates that runtime boot depends on the
public/core contract surface rather than a concrete alternate brain.
"""

from __future__ import annotations

from importlib import import_module

CANON_BOOT_WIRING_ONLY = True
CANON_RUNTIME_BOOT_SELF_CHECK = True
CANON_RUNTIME_BOOT_DECISION_CONTRACT_ONLY = True

def resolve_decision_core_surface():
    return import_module("core.decision_core")


def assert_decision_core_surface_available() -> None:
    surface = resolve_decision_core_surface()
    getattr(surface, "DecisionCore", None)


__all__ = [
    "CANON_BOOT_WIRING_ONLY",
    "CANON_RUNTIME_BOOT_SELF_CHECK",
    "CANON_RUNTIME_BOOT_DECISION_CONTRACT_ONLY",
    "resolve_decision_core_surface",
    "assert_decision_core_surface_available",
]

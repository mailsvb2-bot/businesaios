"""Canonical world-model boot contract.

This surface is wiring-only. It must not host decision logic,
runtime branching, or fallback orchestration.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

WORLD_MODEL_CANON_VERSION = "1.0"
CANON_BOOT_WIRING_ONLY = True
CANON_RUNTIME_WORLD_MODEL_CONTRACT = True

@runtime_checkable
class DecisionWorldModelPort(Protocol):
    def build_world_model(self, *, tenant_id: str | None = None) -> object: ...


__all__ = [
    "WORLD_MODEL_CANON_VERSION",
    "CANON_BOOT_WIRING_ONLY",
    "CANON_RUNTIME_WORLD_MODEL_CONTRACT",
    "DecisionWorldModelPort",
]

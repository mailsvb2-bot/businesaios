"""Runtime boot observability wiring through runtime.observability."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runtime.observability import (
    bind,
    clear,
    configure_structured_logging,
    snapshot,
)

CANON_BOOT_WIRING_ONLY = True
CANON_RUNTIME_BOOT_OBSERVABILITY = True

@dataclass(frozen=True)
class BootObservabilityBundle:
    configure: Any = configure_structured_logging
    bind_context: Any = bind
    clear_context: Any = clear
    snapshot_context: Any = snapshot


def build_boot_observability() -> BootObservabilityBundle:
    return BootObservabilityBundle()


__all__ = [
    "BootObservabilityBundle",
    "CANON_BOOT_WIRING_ONLY",
    "CANON_RUNTIME_BOOT_OBSERVABILITY",
    "build_boot_observability",
]

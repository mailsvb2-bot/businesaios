from __future__ import annotations

CANON_BOOT_FACTORY_CATALOG_OWNER = True
CANON_BOOT_FACTORY_CATALOG_DELEGATES_RUNTIME_BUILDERS = True

"""Boot factory catalog delegation surface.

The concrete runtime service construction remains owned by runtime modules. This
catalog keeps boot/factory wiring discoverable without instantiating runtime
services directly.
"""

from runtime.decision_gateway import build_runtime_decision_gateway
from runtime.decision_input.decision_input_service import build_decision_input_service as build_runtime_decision_input_service
from runtime.decision_input.runtime_state_enrichment import build_runtime_state_enrichment_service

__all__ = [
    "CANON_BOOT_FACTORY_CATALOG_DELEGATES_RUNTIME_BUILDERS",
    "CANON_BOOT_FACTORY_CATALOG_OWNER",
    "build_runtime_decision_gateway",
    "build_runtime_decision_input_service",
    "build_runtime_state_enrichment_service",
]

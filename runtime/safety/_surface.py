"""Canonical runtime safety-controls surface.

Runtime code may build action-control services and construct decision/context
records through this module without binding itself to core safety internals.
"""

from __future__ import annotations

from core.runtime.safe_mode import is_safe_mode
from core.safety.controls.action_context import SafetyActionContext
from core.safety.controls.control_result import ControlDecision, ControlStatus
from core.safety.controls.profile import (
    PersistentSafetyStoreFactory,
    SafetyControlProfile,
    build_default_profile as _build_core_default_profile,
)
from core.safety.controls.service import SafetyControlService
from core.safety.operational.runtime_bootstrap import (
    resolve_operational_safety_runtime as resolve_operational_safety_runtime,
)
from runtime.safety.contract import RUNTIME_SAFETY_PUBLIC_API, SAFETY_CONTROLS_CANON


def build_default_profile(
    *args,
    persistent: bool = False,
    persistent_store_factory: PersistentSafetyStoreFactory | None = None,
    **kwargs,
) -> SafetyControlProfile:
    if persistent and persistent_store_factory is None:
        from runtime.safety.persistence import build_persistent_safety_stores

        persistent_store_factory = lambda threshold: build_persistent_safety_stores(
            repetition_threshold=threshold
        )
    return _build_core_default_profile(
        *args,
        persistent=persistent,
        persistent_store_factory=persistent_store_factory,
        **kwargs,
    )

__all__ = [
    'CANON_RUNTIME_SAFETY_NAMESPACE',
    "ControlDecision",
    "ControlStatus",
    "RUNTIME_SAFETY_PUBLIC_API",
    "SAFETY_CONTROLS_CANON",
    "SafetyActionContext",
    "SafetyControlProfile",
    "SafetyControlService",
    "build_default_profile",
    "is_safe_mode",
]

CANON_RUNTIME_SAFETY_NAMESPACE = True




__all__ = sorted(set(__all__ + ['resolve_operational_safety_runtime']))

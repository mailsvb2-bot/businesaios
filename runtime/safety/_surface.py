from __future__ import annotations

from core.runtime.safe_mode import is_safe_mode
from core.safety.controls.action_context import SafetyActionContext
from core.safety.controls.control_result import ControlDecision, ControlStatus
from core.safety.controls.profile import SafetyControlProfile, build_default_profile
from core.safety.controls.service import SafetyControlService
from runtime.safety.contract import RUNTIME_SAFETY_PUBLIC_API, SAFETY_CONTROLS_CANON

"""Canonical runtime safety-controls surface.

Runtime code may build action-control services and construct decision/context
records through this module without binding itself to core safety internals.
"""

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

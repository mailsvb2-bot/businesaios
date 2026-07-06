from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from application.capability.capability_router import ExecutionCapabilityRouter

CANON_CAPABILITY_AWARE_PLANNING = True


@dataclass(frozen=True)
class CapabilityPlanDecision:
    action_type: str
    payload_patch: dict[str, Any]
    allowed: bool
    fallback_used: bool
    reason: str
    capability: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            'action_type': str(self.action_type),
            'payload_patch': dict(self.payload_patch),
            'allowed': bool(self.allowed),
            'fallback_used': bool(self.fallback_used),
            'reason': str(self.reason),
            'capability': dict(self.capability),
        }


class CapabilityAwarePlanner:
    """Compatibility shim. Canonical owner lives in execution.capability_router."""

    def __init__(self, *, router: ExecutionCapabilityRouter | None = None) -> None:
        self._router = router or ExecutionCapabilityRouter()

    def plan_action(self, *, request: Any, state: Any, action_type: str, payload: Mapping[str, Any] | None) -> CapabilityPlanDecision:
        routed = self._router.route(request=request, state=state, action_type=action_type, payload=payload)
        return CapabilityPlanDecision(
            action_type=routed.action_type,
            payload_patch=dict(routed.payload_patch),
            allowed=bool(routed.allowed),
            fallback_used=bool(routed.fallback_used),
            reason=str(routed.reason),
            capability=dict(routed.capability or {}),
        )


__all__ = ['CANON_CAPABILITY_AWARE_PLANNING', 'CapabilityAwarePlanner', 'CapabilityPlanDecision']

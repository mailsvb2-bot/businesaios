from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CANON_CAPABILITY_FALLBACK_CONTRACT = True


@dataclass(frozen=True)
class CapabilityFallbackDecision:
    kind: str
    public_reason: str
    internal_reason: str
    target_action_type: str = 'notify_owner'
    operator_handoff_required: bool = True
    defer_goal: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            'kind': self.kind,
            'public_reason': self.public_reason,
            'internal_reason': self.internal_reason,
            'target_action_type': self.target_action_type,
            'operator_handoff_required': self.operator_handoff_required,
            'defer_goal': self.defer_goal,
        }


__all__ = ['CANON_CAPABILITY_FALLBACK_CONTRACT', 'CapabilityFallbackDecision']

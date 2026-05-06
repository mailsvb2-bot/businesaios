from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CANON_AUTONOMY_AUDIT = True


@dataclass(frozen=True)
class AutonomyAuditRecord:
    tier_at_decision_time: str
    safety_verdict: str
    violated_limits: tuple[str, ...]
    next_tier_decision: str
    handoff_reason: str | None
    runtime_verdict_matched: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tier_at_decision_time": str(self.tier_at_decision_time),
            "safety_verdict": str(self.safety_verdict),
            "violated_limits": list(self.violated_limits),
            "next_tier_decision": str(self.next_tier_decision),
            "handoff_reason": self.handoff_reason,
            "runtime_verdict_matched": self.runtime_verdict_matched,
        }


__all__ = ["AutonomyAuditRecord", "CANON_AUTONOMY_AUDIT"]

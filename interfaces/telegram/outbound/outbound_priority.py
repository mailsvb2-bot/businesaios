from __future__ import annotations
"""Priority constants and mapping helpers for TelegramOutboundQueue.

Responsibility: single source of truth for priority ladder.
  - PRIO_* constants
  - priority_for(kind) — string → int
  - _normalize_priority(priority) — PriorityArg → int
"""

from interfaces.telegram.outbound.outbound_types import PriorityArg


class OutboundPriorityMixin:
    """Priority ladder + string→int resolution.

    Mix into TelegramOutboundQueue.
    No state; all methods are pure.
    """

    PRIO_ACK: int = 0
    PRIO_UX: int = 10
    PRIO_SYSTEM: int = 20
    PRIO_PAYMENTS: int = 30
    PRIO_NORMAL: int = 50
    PRIO_MARKETING: int = 80
    PRIO_BULK: int = 85
    PRIO_ANALYTICS: int = 90

    @classmethod
    def priority_for(cls, kind: str) -> int:
        """Return canonical priority int for a human-readable kind label."""
        k = (kind or "").strip().lower()
        if k in ("ux", "user", "reply", "menu"):
            return cls.PRIO_UX
        if k in ("system", "infra", "diag"):
            return cls.PRIO_SYSTEM
        if k in ("payments", "payment", "billing"):
            return cls.PRIO_PAYMENTS
        if k in ("marketing", "campaign"):
            return cls.PRIO_MARKETING
        if k in ("bulk", "broadcast", "mass"):
            return cls.PRIO_BULK
        if k in ("analytics", "report", "telemetry"):
            return cls.PRIO_ANALYTICS
        return cls.PRIO_NORMAL

    @classmethod
    def _normalize_priority(cls, priority: PriorityArg) -> int:
        """Coerce PriorityArg (int | str) to an int priority."""
        if isinstance(priority, int):
            return int(priority)
        p = str(priority or "normal").strip().lower()
        if p in {"high", "ack", "spinner"}:
            return cls.PRIO_ACK
        if p in {"ux", "user", "menu"}:
            return cls.PRIO_UX
        if p in {"pay", "payments", "payment"}:
            return cls.PRIO_PAYMENTS
        if p in {"marketing", "bulk"}:
            return cls.PRIO_MARKETING
        return cls.PRIO_NORMAL

    def _priority_label(self, prio: int) -> str:
        """Map a numeric priority to a human-readable bucket label."""
        if prio <= self.PRIO_UX:
            return "ux"
        if prio <= self.PRIO_SYSTEM:
            return "system"
        if prio <= self.PRIO_PAYMENTS:
            return "payments"
        if prio >= self.PRIO_ANALYTICS:
            return "analytics"
        if prio >= self.PRIO_BULK:
            return "bulk"
        if prio >= self.PRIO_MARKETING:
            return "marketing"
        return "normal"

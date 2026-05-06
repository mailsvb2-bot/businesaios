from __future__ import annotations

from dataclasses import dataclass

from ..enums import GuardSeverity
from ..guard import GuardTrigger
from ..types import MarginSnapshot


@dataclass
class NegativeMarginGuard:
    def check(self, margin: MarginSnapshot) -> GuardTrigger | None:
        if margin.net_margin_ratio < 0:
            return GuardTrigger(
                code="negative_margin",
                severity=GuardSeverity.BLOCK,
                message="Net margin is negative; growth expansion must be constrained.",
                details={"net_margin_ratio": margin.net_margin_ratio},
            )
        return None

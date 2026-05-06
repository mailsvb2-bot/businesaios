from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StopLossPolicy:
    """Traffic stop-loss (ads specific)."""

    max_spend_minor_no_conv: int = 0

    def triggered(self, *, spend_minor_window: int, conversions_window: int) -> bool:
        if int(self.max_spend_minor_no_conv or 0) <= 0:
            return False
        if int(conversions_window or 0) > 0:
            return False
        return int(spend_minor_window or 0) >= int(self.max_spend_minor_no_conv)

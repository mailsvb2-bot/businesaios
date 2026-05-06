from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BidManager:
    """Bid hints.

    We keep this tiny: platform-specific bid strategies are set by connectors.
    """
    def initial_bid_hint(self, *, target_cac_minor: int) -> dict:
        # A hint only; connector may ignore.
        return {"target_cac_minor": int(target_cac_minor or 0)}

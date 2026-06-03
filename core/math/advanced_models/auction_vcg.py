from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence


@dataclass(frozen=True)
class Bid:
    bidder_id: str
    value: float

@dataclass(frozen=True)
class AuctionOutcome:
    winner_id: str
    charged_price: float
    winning_value: float

def allocate_single_slot_vcg(bids: Sequence[Bid]) -> AuctionOutcome:
    if len(bids) < 2:
        raise ValueError("at least two bids are required for meaningful VCG pricing")
    sorted_bids = sorted(bids, key=lambda b: b.value, reverse=True)
    winner = sorted_bids[0]
    second_price = sorted_bids[1].value
    return AuctionOutcome(
        winner_id=winner.bidder_id,
        charged_price=float(second_price),
        winning_value=float(winner.value),
    )

from __future__ import annotations

from runtime.market.market_snapshot import MarketSnapshot


def build_market_state(snapshot: MarketSnapshot) -> dict[str, float]:
    return {
        "global_macro_score": float(snapshot.global_macro_score),
        "global_micro_score": float(snapshot.global_micro_score),
        "global_competitive_shift": float(snapshot.global_competitive_shift),
        "segment_count": float(len(snapshot.segment_states)),
    }

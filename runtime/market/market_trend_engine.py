from __future__ import annotations

from collections import defaultdict

from runtime.market.market_snapshot import MarketSnapshot
from runtime.market.segment_trend_state import SegmentTrendState
from runtime.market.trend_signal import TrendSignal


def _clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


class MarketTrendEngine:
    def inspect(self, signals: tuple[TrendSignal, ...]) -> MarketSnapshot:
        if not signals:
            return MarketSnapshot(
                global_macro_score=0.0,
                global_micro_score=0.0,
                global_competitive_shift=0.0,
                segment_states=(),
            )

        grouped: dict[str, list[TrendSignal]] = defaultdict(list)
        for item in signals:
            grouped[item.segment_key].append(item)

        states: list[SegmentTrendState] = []
        for segment_key, entries in grouped.items():
            demand = sum(max(-1.0, min(1.0, e.demand_delta)) * max(0.0, e.recency_weight) for e in entries)
            conversion = sum(max(-1.0, min(1.0, e.conversion_delta)) * max(0.0, e.recency_weight) for e in entries)
            media_cost = sum(max(-1.0, min(1.0, (e.cpm_delta + e.cpc_delta) / 2.0)) for e in entries)
            competition = sum(max(0.0, min(1.0, e.competitor_pressure)) for e in entries)

            count = float(max(1, len(entries)))
            macro_score = _clamp_unit(0.50 + ((0.55 * demand) - (0.20 * media_cost)) / count)
            micro_score = _clamp_unit(0.50 + ((0.60 * conversion) - (0.15 * media_cost)) / count)
            persistence_score = _clamp_unit(
                sum(1.0 for e in entries if e.demand_delta > 0.0 and e.conversion_delta >= 0.0) / count
            )
            competitive_shift_score = _clamp_unit(competition / count)

            states.append(
                SegmentTrendState(
                    segment_key=segment_key,
                    macro_score=macro_score,
                    micro_score=micro_score,
                    persistence_score=persistence_score,
                    competitive_shift_score=competitive_shift_score,
                )
            )

        global_macro = sum(s.macro_score for s in states) / float(len(states))
        global_micro = sum(s.micro_score for s in states) / float(len(states))
        global_shift = sum(s.competitive_shift_score for s in states) / float(len(states))

        return MarketSnapshot(
            global_macro_score=_clamp_unit(global_macro),
            global_micro_score=_clamp_unit(global_micro),
            global_competitive_shift=_clamp_unit(global_shift),
            segment_states=tuple(states),
        )

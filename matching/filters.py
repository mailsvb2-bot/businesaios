from __future__ import annotations

from config.demand_thresholds import MATCH_BLOCK_RISK_THRESHOLD
from config.routing_limits import ROUTING_SCORE_FLOOR


class MatchThresholds:
    def floor(self) -> float:
        return float(ROUTING_SCORE_FLOOR)

    def block_risk_threshold(self) -> float:
        return float(MATCH_BLOCK_RISK_THRESHOLD)


class MatchFilter:
    def __init__(self, *, thresholds: MatchThresholds | None = None) -> None:
        self._thresholds = thresholds or MatchThresholds()

    def allow(self, candidate: object) -> bool:
        return (not bool(candidate.blocked)) and float(candidate.score) >= self._thresholds.floor()


class MatchFilters:
    def __init__(self, *, thresholds: MatchThresholds | None = None) -> None:
        self._thresholds = thresholds or MatchThresholds()
        self._candidate_filter = MatchFilter(thresholds=self._thresholds)

    def is_blocked(self, *, profile, live_state, finite) -> bool:
        return (
            (not profile.active)
            or finite(live_state.risk_score) >= self._thresholds.block_risk_threshold()
            or (not live_state.open_now)
        )

    def allow(self, candidate: object) -> bool:
        return self._candidate_filter.allow(candidate)

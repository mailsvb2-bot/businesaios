from __future__ import annotations

# Canonical owner remains growth.seo.rank_tracking.
from growth.seo import RankTracking as GrowthRankTracking


class RankTracking:
    def __init__(self, *, tracker: GrowthRankTracking | None = None) -> None:
        self._tracker = tracker or GrowthRankTracking()

    def record(self, keyword: str, position: int) -> dict[str, object]:
        payload = {"keyword": str(keyword), "position": int(position)}
        observation = self._tracker.observe(payload)
        return {
            "keyword": payload["keyword"],
            "position": payload["position"],
            "observation": observation,
        }

from __future__ import annotations

from dataclasses import dataclass, field
import random
from collections.abc import Iterable, Mapping


CANON_MARKET_INTELLIGENCE_SAMPLING = True


@dataclass(frozen=True)
class SamplingCandidate:
    provider: str
    source_family: str
    priority: float = 0.5
    exploration_bias: float = 0.1
    metadata: Mapping[str, object] = field(default_factory=dict)


class AdaptiveSamplingStrategy:
    def rank_candidates(self, candidates: Iterable[SamplingCandidate], *, limit: int = 5) -> tuple[SamplingCandidate, ...]:
        items = list(candidates)
        if not items:
            return ()
        scored: list[tuple[float, SamplingCandidate]] = []
        for item in items:
            score = max(0.0, min(float(item.priority), 1.0)) + random.uniform(0.0, max(0.0, min(float(item.exploration_bias), 1.0)))
            scored.append((score, item))
        scored.sort(key=lambda pair: (-pair[0], pair[1].provider, pair[1].source_family))
        return tuple(item for _, item in scored[: max(1, int(limit))])


AdaptiveSamplingStrategy.select = AdaptiveSamplingStrategy.rank_candidates

__all__ = ['CANON_MARKET_INTELLIGENCE_SAMPLING', 'AdaptiveSamplingStrategy', 'SamplingCandidate']

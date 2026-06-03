from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from collections.abc import Mapping, Sequence

from .contracts import AdsRLAction, AdsRLState
from .policy import AdsRLPolicy, PolicyDecision


def action_key(action: AdsRLAction) -> str:
    """Stable arm id for an action."""
    parts = [
        str(action.campaign_id or ""),
        str(action.daily_budget) if action.daily_budget is not None else "",
        str(action.bid_cap) if action.bid_cap is not None else "",
        str(action.cpa_target) if action.cpa_target is not None else "",
        str(action.creative_id or ""),
        str(action.audience_id or ""),
        str(action.objective or ""),
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


@dataclass(frozen=True)
class ArmStat:
    pulls: int
    reward_sum: float

    @property
    def mean(self) -> float:
        if self.pulls <= 0:
            return 0.0
        return float(self.reward_sum) / float(self.pulls)


class UCB1Policy(AdsRLPolicy):
    """UCB1 over finite actions.

    This is *not* full RL, but it is a production-safe stepping stone:
    - finite action space
    - interpretable stats
    - supports continuous reward
    - easy to evaluate off-policy

    We call it RL in the product sense (closed loop control), but the primitive
    remains a contextual bandit, which is the safest default for ads knobs.
    """

    def __init__(self, *, policy_id: str, stats: Mapping[str, ArmStat] | None, seed: str) -> None:
        self._policy_id = str(policy_id or "ucb1@v1")
        self._stats = dict(stats or {})
        self._seed = str(seed or "")

    def select_action(self, *, state: AdsRLState, actions: Sequence[AdsRLAction]) -> PolicyDecision:
        if not actions:
            raise ValueError("actions must be non-empty")

        # Exploration first: pick any arm never pulled.
        for a in actions:
            k = action_key(a)
            st = self._stats.get(k)
            if st is None or int(st.pulls) <= 0:
                return PolicyDecision(self._policy_id, a, 0.2, "explore_unseen_arm")

        current_keys = {action_key(a) for a in actions}
        n = sum(
            int(st.pulls)
            for k, st in self._stats.items()
            if st is not None and k in current_keys
        )
        n = max(1, int(n))

        best = actions[0]
        best_score = -1e18
        best_mean = 0.0
        for a in actions:
            k = action_key(a)
            st = self._stats.get(k) or ArmStat(0, 0.0)
            pulls = max(1, int(st.pulls))
            bonus = math.sqrt((2.0 * math.log(float(n))) / float(pulls))
            score = float(st.mean) + bonus
            if score > best_score:
                best_score = score
                best = a
                best_mean = float(st.mean)

        conf = max(0.05, min(0.95, 0.5 + (best_mean / (1.0 + abs(best_mean))) * 0.4))
        return PolicyDecision(self._policy_id, best, float(conf), "ucb1")

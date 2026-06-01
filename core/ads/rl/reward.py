from __future__ import annotations

from dataclasses import dataclass

from core.ads.rl.dataset import Transition
from core.governance.evaluators.profit_metrics import ProfitMetricsService


@dataclass(frozen=True)
class RewardWindow:
    pre_days: int = 3
    post_days: int = 3


class RewardComputer:
    def __init__(self, *, profit_metrics: ProfitMetricsService, window: RewardWindow | None = None) -> None:
        self._pm = profit_metrics
        self._w = window or RewardWindow()

    def transition_for_decision(self, *, tenant_id: str, decision_id: str, lookback_days: int) -> Transition | None:
        pre = self._pm.profit_lookback(tenant_id=str(tenant_id), lookback_days=int(self._w.pre_days))
        post = self._pm.profit_lookback(tenant_id=str(tenant_id), lookback_days=int(self._w.post_days))
        reward_minor = int(post.profit_minor) - int(pre.profit_minor)
        state = {
            "revenue_minor": int(post.revenue_minor),
            "ads_spend_minor": int(post.ads_spend_minor),
            "profit_minor": int(post.profit_minor),
            "lookback_days": int(lookback_days),
        }
        action = {
            "kind": "ads.plan",
            "decision_id": str(decision_id),
        }
        meta = {
            "tenant_id": str(tenant_id),
            "decision_id": str(decision_id),
            "reward_pre_minor": int(pre.profit_minor),
            "reward_post_minor": int(post.profit_minor),
        }
        return Transition(state=state, action=action, reward_minor=int(reward_minor), meta=meta)

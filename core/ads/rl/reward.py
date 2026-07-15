from __future__ import annotations

import time
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
        tenant = str(tenant_id).strip()
        decision = str(decision_id).strip()
        if not tenant or not decision:
            return None
        pre_days = max(1, int(self._w.pre_days))
        post_days = max(1, int(self._w.post_days))
        day_ms = 24 * 60 * 60 * 1000
        anchor_ms = self._pm.decision_executed_at_ms(
            tenant_id=tenant,
            decision_id=decision,
        )
        if anchor_ms is None:
            return None
        pre_start_ms = int(anchor_ms) - pre_days * day_ms
        post_end_ms = int(anchor_ms) + post_days * day_ms
        observed_ms = int(time.time() * 1000)
        if observed_ms < post_end_ms:
            return None

        pre = self._pm.profit_between_ms(
            tenant_id=tenant,
            start_ms=pre_start_ms,
            end_ms=int(anchor_ms),
        )
        post = self._pm.profit_between_ms(
            tenant_id=tenant,
            start_ms=int(anchor_ms),
            end_ms=post_end_ms,
        )
        reward_minor = int(post.profit_minor) - int(pre.profit_minor)
        state = {
            "revenue_minor": int(post.revenue_minor),
            "ads_spend_minor": int(post.ads_spend_minor),
            "profit_minor": int(post.profit_minor),
            "lookback_days": max(1, int(lookback_days)),
        }
        action = {
            "kind": "ads.plan",
            "decision_id": decision,
        }
        meta = {
            "tenant_id": tenant,
            "decision_id": decision,
            "reward_pre_minor": int(pre.profit_minor),
            "reward_post_minor": int(post.profit_minor),
            "reward_anchor_ms": int(anchor_ms),
            "reward_pre_start_ms": int(pre_start_ms),
            "reward_post_end_ms": int(post_end_ms),
            "reward_observed_ms": int(observed_ms),
            "reward_pre_days": int(pre_days),
            "reward_post_days": int(post_days),
            "reward_source": "canonical_profit_windows",
        }
        return Transition(state=state, action=action, reward_minor=int(reward_minor), meta=meta)

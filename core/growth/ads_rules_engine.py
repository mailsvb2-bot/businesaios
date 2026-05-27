from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional

from config.ads_aggregates_policy import DEFAULT_ADS_AGGREGATES_POLICY
from config.ads_rules_policy import DEFAULT_ADS_RULES_POLICY, AdsRulesPolicy
from core.growth.ads_aggregates import AdsAggregates
from core.growth.recommendations import AdsObjectRef, AdsRecommendation


@dataclass(frozen=True)
class RuleTargets:
    target_cpa: Optional[float] = None
    min_conversions_for_scale: int = DEFAULT_ADS_RULES_POLICY.min_conversions_for_scale
    scale_step_pct: float = DEFAULT_ADS_RULES_POLICY.scale_step_pct
    stop_loss_spend: float = DEFAULT_ADS_RULES_POLICY.stop_loss_spend


class RulesBasedRecommendationEngine:
    def __init__(self, *, aggs: AdsAggregates, cfg: RuleTargets, policy: AdsRulesPolicy | None = None):
        self._aggs = aggs
        self._cfg = cfg
        self._policy = policy or DEFAULT_ADS_RULES_POLICY

    def propose(self, *, tenant_id: str, platform: str, account_id: str) -> List[AdsRecommendation]:
        day = (date.today() - timedelta(days=int(self._policy.yesterday_days_offset))).isoformat()
        by_campaign = self._aggs.by_campaign_day(tenant_id=tenant_id, day_iso=day)
        recs: List[AdsRecommendation] = []

        for cid, agg in by_campaign.items():
            if agg.spend >= self._cfg.stop_loss_spend and agg.conversions <= DEFAULT_ADS_AGGREGATES_POLICY.default_conversions:
                recs.append(
                    AdsRecommendation(
                        rec_id=str(uuid.uuid4()),
                        title="Stop-loss: reduce budget for non-converting campaign",
                        rationale=f"Yesterday spend={agg.spend:.2f} with {DEFAULT_ADS_AGGREGATES_POLICY.default_conversions} conversions.",
                        target=AdsObjectRef(platform=platform, account_id=account_id, object_type="campaign", object_id=cid),
                        patch={"campaign_id": cid, "daily_budget_delta_pct": float(self._policy.stop_loss_budget_delta_pct)},
                        expected_impact={"risk_reduction": True},
                        risk_notes="Check tracking/conversion setup.",
                    )
                )
                continue

            if self._cfg.target_cpa is not None:
                cpa = agg.cpa()
                if cpa is not None and cpa <= self._cfg.target_cpa and agg.conversions >= self._cfg.min_conversions_for_scale:
                    step = float(self._cfg.scale_step_pct)
                    recs.append(
                        AdsRecommendation(
                            rec_id=str(uuid.uuid4()),
                            title="Scale winners: increase budget slightly",
                            rationale=f"Yesterday CPA={cpa:.2f} <= target {self._cfg.target_cpa:.2f}, conv={agg.conversions}.",
                            target=AdsObjectRef(platform=platform, account_id=account_id, object_type="campaign", object_id=cid),
                            patch={"campaign_id": cid, "daily_budget_delta_pct": step},
                            expected_impact={"delta_budget_pct": step, "hypothesis": "more volume at similar CPA"},
                            risk_notes="Scale gradually; watch CPA drift.",
                        )
                    )
        return recs

from __future__ import annotations

from dataclasses import dataclass, field

from shared.numbers import coerce_float
from governance.economic.action_economics_model import ActionEconomicsIntent, ActionEconomicsSnapshot
from governance.economic.economic_policy_contract import EconomicPolicyConfig

CANON_NON_DECISION_MODULE = True


@dataclass(frozen=True)
class PortfolioBudgetAllocator:
    config: EconomicPolicyConfig = field(default_factory=EconomicPolicyConfig)

    def allocate(self, *, snapshot: ActionEconomicsSnapshot, intent: ActionEconomicsIntent) -> dict[str, float]:
        explicit_budgets = {
            str(k): coerce_float(v, 0.0, minimum=0.0)
            for k, v in snapshot.portfolio_budgets.items()
            if coerce_float(v, 0.0, minimum=0.0) > 0.0
        }
        if explicit_budgets:
            return explicit_budgets
        total_budget = max(0.0, float(snapshot.planned_spend or 0.0))
        if total_budget <= 0.0:
            if intent.channel:
                return {intent.channel: round(max(0.0, intent.requested_budget, intent.budget_delta), 2)}
            return {}
        candidate_channels = set(snapshot.portfolio_weights.keys()) | {intent.channel or "default"}
        if not candidate_channels:
            candidate_channels = {"default"}
        scores: dict[str, float] = {}
        for channel in candidate_channels:
            base_weight = max(0.0, float(snapshot.portfolio_weights.get(channel, 1.0)))
            risk_score = max(0.0, float(snapshot.channel_risk_scores.get(channel, 0.0)))
            roi_component = max(0.0, intent.expected_incremental_roi) * self.config.allocation_roi_weight
            margin_component = max(0.0, snapshot.gross_margin) * self.config.allocation_margin_weight
            priority_component = (max(0, intent.priority) / 100.0) * self.config.allocation_priority_weight
            risk_penalty = risk_score * self.config.allocation_risk_penalty
            score = max(0.0, base_weight + roi_component + margin_component + priority_component - risk_penalty)
            scores[channel] = score
        denom = sum(scores.values())
        if denom <= 0.0:
            equal = round(total_budget / len(scores), 2)
            return {channel: equal for channel in scores}
        return {channel: round(total_budget * (score / denom), 2) for channel, score in scores.items()}

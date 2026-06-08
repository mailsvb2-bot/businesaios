from __future__ import annotations

from dataclasses import dataclass

from .contracts import TrafficAudience, TrafficBudget, TrafficCampaignSpec, TrafficCreative, TrafficObjective


@dataclass(frozen=True)
class CampaignFactory:
    """Deterministic campaign skeleton builder.

    No platform logic here. Pure mapping from business inputs to a normalized spec.
    """

    def build(
        self,
        *,
        name: str,
        objective_kind: str,
        target_cac_minor: int,
        currency: str,
        daily_budget_minor: int,
        budget_currency: str,
        audience_region: str,
        creative: TrafficCreative,
        destination: dict,
        interests: list[str] | None = None,
    ) -> TrafficCampaignSpec:
        obj = TrafficObjective(kind=str(objective_kind), target_cac_minor=int(target_cac_minor or 0), currency=str(currency))
        budget = TrafficBudget(daily_budget_minor=int(daily_budget_minor), currency=str(budget_currency))
        audience = TrafficAudience(region=str(audience_region or ""), interests=list(interests or []), raw={"region": str(audience_region or "")})
        return TrafficCampaignSpec(
            name=str(name),
            objective=obj,
            budget=budget,
            audience=audience,
            creative=creative,
            destination=dict(destination or {}),
        )

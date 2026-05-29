from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from core.ads.ads_service import AdsPlan, AdsService

from .contracts import TrafficPlan


@dataclass(frozen=True)
class AdsSpecBuilder:
    """Translate TrafficPlan -> AdsService spec dict.

    Keep this *connector-neutral*: action names are generic.
    Connector implementations decide how to map them to their native API.
    """

    def to_spec(self, *, plan: TrafficPlan) -> dict[str, Any]:
        c = plan.campaign
        return {
            "notes": plan.notes,
            "commands": [
                {
                    "platform": plan.platform,
                    "action": "create_campaign",
                    "payload": {
                        "account_id": plan.account_id,
                        "name": c.name,
                        "objective": {"kind": c.objective.kind, "target_cac_minor": c.objective.target_cac_minor, "currency": c.objective.currency},
                        "budget": {"daily_budget_minor": c.budget.daily_budget_minor, "currency": c.budget.currency},
                        "audience": {"region": c.audience.region, "interests": list(c.audience.interests), "raw": dict(c.audience.raw or {})},
                        "creative": {"headline": c.creative.headline, "primary_text": c.creative.primary_text, "cta": c.creative.cta},
                        "destination": dict(c.destination or {}),
                        "metadata": dict(plan.metadata or {}),
                    },
                }
            ],
        }

    def build_ads_plan(self, *, ads: AdsService, tenant_id: str, plan: TrafficPlan) -> AdsPlan:
        spec = self.to_spec(plan=plan)
        return ads.build_plan(tenant_id=tenant_id, spec=spec)

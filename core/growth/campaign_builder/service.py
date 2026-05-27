from __future__ import annotations

from dataclasses import dataclass

from contracts.autopilot_contract import AutopilotContract
from core.autopilot.resolver import resolve_autopilot_contract
from core.traffic.strategy_service import TrafficStrategyService

from .budgeting import CampaignBudgetPolicy
from .contracts import AutopilotCampaignBuildRequest, AutopilotCampaignBuildResult
from .spec_codec import TrafficToAdsSpec
from .validation import validate_build_request


@dataclass(frozen=True)
class AutopilotCampaignBuilder:
    """Autopilot Campaign Builder (deterministic, no provider imports).

    Responsibilities:
      - validate request
      - resolve tenant autopilot constraints
      - clamp budgets to constraints
      - build a TrafficPlan using TrafficStrategyService
      - translate to AdsService spec dict (connector-neutral)
    """

    traffic: TrafficStrategyService
    codec: TrafficToAdsSpec
    budget_policy: CampaignBudgetPolicy

    def build(
        self,
        *,
        req: AutopilotCampaignBuildRequest,
        autopilot_contract: AutopilotContract | None = None,
    ) -> AutopilotCampaignBuildResult:
        validate_build_request(req)

        c = autopilot_contract or resolve_autopilot_contract(tenant_id=str(req.tenant_id))
        cbudget = self.budget_policy.budget_from_constraints(c.constraints)
        total_minor_7d = self.budget_policy.clamp_total_budget_minor_7d(total_budget_minor_7d=int(req.total_budget_minor_7d), constraints=cbudget)

        plan = self.traffic.plan_7d(
            tenant_id=str(req.tenant_id),
            platform=str(req.platform),
            account_id=str(req.account_id),
            what=str(req.what),
            offer_title=str(req.offer_title),
            region=str(req.region),
            total_budget_minor_7d=int(total_minor_7d),
            budget_currency=str(req.budget_currency),
            target_cac_minor=int(req.target_cac_minor or 0),
            destination=dict(req.destination or {}),
            seed=str(req.seed or "v1"),
        )
        spec = self.codec.encode(plan=plan)
        return AutopilotCampaignBuildResult(traffic_plan=plan, ads_spec=spec, notes="autopilot_campaign_builder@v1")

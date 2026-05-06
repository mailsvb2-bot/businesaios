from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class ActionSafetySpec:
    action_prefix: str
    blast_financial_amount: float = 0.0
    blast_users_affected: int = 0
    blast_records_affected: int = 0
    blast_services_touched: int = 0
    default_estimated_cost: float = 0.0
    simulation_required: bool = False
    approval_required: bool = False
    high_impact: bool = False


@dataclass(frozen=True)
class ActionSafetyCatalog:
    specs: Mapping[str, ActionSafetySpec] = field(default_factory=dict)

    def resolve(self, action: str) -> ActionSafetySpec | None:
        name = str(action or "")
        for prefix, spec in self.specs.items():
            if name.startswith(prefix):
                return spec
        return None


def build_default_action_catalog() -> ActionSafetyCatalog:
    specs = {
        "capture_payment": ActionSafetySpec(
            action_prefix="capture_payment",
            blast_financial_amount=100.0,
            blast_users_affected=1,
            blast_records_affected=10,
            blast_services_touched=1,
            default_estimated_cost=10.0,
            approval_required=False,
            simulation_required=True,
            high_impact=True,
        ),
        "apply_pricing_change": ActionSafetySpec(
            action_prefix="apply_pricing_change",
            blast_financial_amount=500.0,
            blast_users_affected=200,
            blast_records_affected=100,
            blast_services_touched=1,
            default_estimated_cost=25.0,
            approval_required=False,
            simulation_required=True,
            high_impact=True,
        ),
        "deploy_policy": ActionSafetySpec(
            action_prefix="deploy_policy",
            blast_financial_amount=250.0,
            blast_users_affected=50,
            blast_records_affected=100,
            blast_services_touched=2,
            default_estimated_cost=5.0,
            approval_required=True,
            simulation_required=True,
            high_impact=True,
        ),
        "rollback_policy": ActionSafetySpec(
            action_prefix="rollback_policy",
            blast_financial_amount=250.0,
            blast_users_affected=50,
            blast_records_affected=100,
            blast_services_touched=2,
            default_estimated_cost=5.0,
            approval_required=True,
            simulation_required=True,
            high_impact=True,
        ),
        "send_marketing_offer": ActionSafetySpec(
            action_prefix="send_marketing_offer",
            blast_financial_amount=500.0,
            blast_users_affected=250,
            blast_records_affected=250,
            blast_services_touched=1,
            default_estimated_cost=1.0,
            simulation_required=True,
            high_impact=True,
        ),
        "ads_apply_": ActionSafetySpec(
            action_prefix="ads_apply_",
            blast_financial_amount=500.0,
            blast_users_affected=500,
            blast_records_affected=100,
            blast_services_touched=2,
            default_estimated_cost=20.0,
            approval_required=True,
            simulation_required=True,
            high_impact=True,
        ),
    }
    return ActionSafetyCatalog(specs=specs)

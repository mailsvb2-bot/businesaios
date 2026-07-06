"""AI CEO orchestration helpers.

AI CEO is a *planning assistant*, not an executor.
All irreversible actions must still go through DecisionCore -> Runtime.

This module provides tiny helper(s) that can be used by UI flows.
"""

from __future__ import annotations

from core.ai_ceo.contracts import CEOIntentV1, CEOPlanStepV1
from core.ai_ceo.ledger import GrowthSnapshotV1
from core.ai_ceo.planner_support import build_default_plan_steps


def build_minimal_plan_steps(
    *, tenant_id: str, user_id: str, snapshot: GrowthSnapshotV1, intent: CEOIntentV1 | None
) -> list[CEOPlanStepV1]:
    """Conservative default steps.

    Invariant:
    - no direct ads_apply_execute here (avoids bypassing Ads Apply gate UI)
    - service and planner use one canonical step shape
    """
    _ = snapshot
    _ = intent
    return build_default_plan_steps(
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        locale="ru",
        channel="telegram",
        offer={
            "offer_id": "profit_sprint_default",
            "title": "Profit Sprint",
            "price_minor": 0,
            "currency": "RUB",
        },
        plan_id="service_minimal_plan",
        dry_run=True,
    )

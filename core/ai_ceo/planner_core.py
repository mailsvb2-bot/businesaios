from __future__ import annotations

from core.ai_ceo.contracts import CEOIntentV1, CEOPlanV1
from core.ai_ceo.ledger import GrowthSnapshotV1
from core.ai_ceo.planner_support import build_plan
from core.ai_ceo.safety import AutonomyPolicyV1
from kernel.world_state import WorldStateV1

CANON_AI_CEO_PLANNER_CORE = True

def build_ceo_plan(
    *,
    state: WorldStateV1,
    snapshot: GrowthSnapshotV1,
    autonomy: AutonomyPolicyV1,
    bot_username: str = "",
    intent: CEOIntentV1 | None = None,
    plan_id: str = "",
) -> CEOPlanV1:
    _ = bot_username
    return build_plan(
        state,
        snapshot=snapshot,
        autonomy=autonomy,
        intent=intent,
        plan_id=str(plan_id).strip() or "ai_ceo_plan",
    )

__all__ = ["CANON_AI_CEO_PLANNER_CORE", "build_ceo_plan"]

from __future__ import annotations

"""AI CEO planner (pure, advisory-only).

DecisionCore remains the single issuer. AI CEO only assembles a reviewable plan.
"""

from core.ai_ceo.contracts import CEOIntentV1, CEOPlanV1
from core.ai_ceo.ledger import GrowthSnapshotV1
from core.ai_ceo.ledger import to_dict as snapshot_to_dict
from core.ai_ceo.planner_support import (
    CEOContextReader,
    CEOPlanBuilder,
    apply_policy_and_rank,  # lock/test marker: planner remains aligned with shared policy surface
    build_plan_summary,
    build_plan_targets,
    render_plan_text,
)
from core.ai_ceo.safety import AutonomyPolicyV1
from core.ai_ceo.scoring import rank_steps  # compatibility export for resilience tests
from kernel.world_state import WorldStateV1


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
    used_intent = intent or CEOContextReader.default_intent_from_state(state)
    resolved_plan_id = str(plan_id).strip() or "ai_ceo_plan"
    builder = CEOPlanBuilder(state=state, autonomy=autonomy, plan_id=resolved_plan_id)
    raw_steps = builder.build_steps()
    final_steps = apply_policy_and_rank(
        steps=raw_steps,
        autonomy=autonomy,
        snapshot=snapshot,
    )
    return CEOPlanV1(
        plan_id=resolved_plan_id,
        intent=used_intent,
        summary=build_plan_summary(),
        steps=final_steps,
        kpi_before=snapshot_to_dict(snapshot),
        kpi_targets=build_plan_targets(intent=used_intent),
    )


__all__ = ["build_ceo_plan", "render_plan_text", "rank_steps"]

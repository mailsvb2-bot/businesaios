from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True

from runtime.actions import ACTION_AI_CEO_PLAN_V1
from runtime.handlers import ActionHandlerRegistry


def register_core_handlers(*, handlers: ActionHandlerRegistry, ctx) -> None:
    from runtime.handlers.ai_ceo_plan import handle_ai_ceo_plan
    from runtime.handlers.pricing_select import handle_pricing_select
    from runtime.handlers.reward_observe import handle_reward_observe
    from runtime.handlers.growth_propose import handle_growth_propose
    from runtime.boot.handler_groups.shared import get_ctx_value

    handlers.register(
        ACTION_AI_CEO_PLAN_V1,
        lambda payload, effects, env: handle_ai_ceo_plan(
            payload,
            effects,
            env,
            planner=get_ctx_value(ctx, "ai_ceo_planner"),
        ),
    )
    handlers.register(
        "pricing_select@v1",
        lambda payload, effects, env: handle_pricing_select(
            payload,
            effects,
            env,
            selection_service=get_ctx_value(ctx, "pricing_selection_service"),
        ),
    )
    handlers.register(
        "reward_observe@v1",
        lambda payload, effects, env: handle_reward_observe(
            payload,
            effects,
            env,
            observer=get_ctx_value(ctx, "reward_observer"),
        ),
    )
    handlers.register(
        "growth_propose@v1",
        lambda payload, effects, env: handle_growth_propose(
            payload,
            effects,
            env,
            proposal_service=get_ctx_value(ctx, "growth_proposal_service"),
            proposal_gateway=get_ctx_value(ctx, "proposal_gateway"),
        ),
    )

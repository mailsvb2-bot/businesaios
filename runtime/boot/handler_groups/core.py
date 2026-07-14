from __future__ import annotations

from runtime.handlers import ActionHandlerRegistry

CANON_BOOT_WIRING_ONLY = True
_AI_CEO_HANDLER_REF = "runtime.handlers.ai_ceo_plan:handle_ai_ceo_plan"


def _catalog_action_for_handler(handler_ref: str) -> str:
    from runtime.boot.actions_catalog import SPEC_ROWS

    for name, ref, *_rest in SPEC_ROWS:
        if str(ref) == str(handler_ref):
            return str(name)
    raise KeyError(handler_ref)


def _track_marker_event(*, payload, effects, env, event_type: str):
    body = dict(payload or {})
    event_payload = dict(body.get("payload") or {}) if isinstance(body.get("payload"), dict) else {}
    tenant_id = str(body.get("tenant_id") or "").strip()
    product_id = str(body.get("product_id") or "").strip()
    if tenant_id:
        event_payload.setdefault("tenant_id", tenant_id)
    if product_id:
        event_payload.setdefault("product_id", product_id)
    return effects.track_event(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        user_id=str(body.get("user_id") or "system"),
        event_type=str(body.get("event_type") or event_type),
        payload=event_payload,
        source=str(body.get("source") or "autopilot"),
    )


def register_core_handlers(*, handlers: ActionHandlerRegistry, ctx) -> None:
    from runtime.boot.handler_groups.shared import get_ctx_value
    from runtime.handlers.ai_ceo_plan import handle_ai_ceo_plan
    from runtime.handlers.growth_propose import handle_growth_propose
    from runtime.handlers.pricing_select import handle_pricing_select
    from runtime.handlers.reward_observe import handle_reward_observe

    handlers.register(
        _catalog_action_for_handler(_AI_CEO_HANDLER_REF),
        lambda payload, effects, env: handle_ai_ceo_plan(
            payload,
            effects,
            env,
            planner=get_ctx_value(ctx, "ai_ceo_planner"),
        ),
    )
    handlers.register(
        "autopilot_started@v1",
        lambda payload, effects, env: _track_marker_event(
            payload=payload,
            effects=effects,
            env=env,
            event_type="autopilot_started",
        ),
    )
    handlers.register(
        "autopilot_run_started@v1",
        lambda payload, effects, env: _track_marker_event(
            payload=payload,
            effects=effects,
            env=env,
            event_type="autopilot_run_started",
        ),
    )
    handlers.register(
        "autopilot_decision@v1",
        lambda payload, effects, env: _track_marker_event(
            payload=payload,
            effects=effects,
            env=env,
            event_type="autopilot_decision",
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

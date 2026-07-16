from __future__ import annotations

from runtime.handlers import ActionHandlerRegistry

CANON_BOOT_WIRING_ONLY = True


def register_growth_handlers(*, handlers: ActionHandlerRegistry, event_store, behavior_graph_store, marketing_llm) -> None:
    from runtime.handlers.behavior_graph import (
        handle_behavior_graph_build,
        handle_behavior_graph_neighbors,
        handle_behavior_graph_node,
        handle_behavior_graph_path,
        handle_behavior_graph_reset,
    )
    from runtime.handlers.growth_propose import handle_growth_propose as _growth_propose
    from runtime.handlers.growth_strategy_backlog import handle_growth_strategy_backlog as _growth_backlog
    from runtime.handlers.growth_strategy_generate import handle_growth_strategy_generate as _growth_generate
    from runtime.handlers.growth_strategy_state import (
        handle_growth_strategy_accept as _growth_accept,
    )
    from runtime.handlers.growth_strategy_state import (
        handle_growth_strategy_reject as _growth_reject,
    )
    from runtime.handlers.profit_sprint_onboarding import (
        handle_onboarding_lead_source as _ps_lead,
    )
    from runtime.handlers.profit_sprint_onboarding import (
        handle_onboarding_start as _ps_start,
    )
    from runtime.handlers.profit_sprint_onboarding import (
        handle_onboarding_text as _ps_text,
    )

    handlers.register("profit_sprint_onboarding_start@v1", _ps_start)
    handlers.register("profit_sprint_onboarding_text@v1", _ps_text)
    handlers.register("profit_sprint_onboarding_lead_source@v1", _ps_lead)

    handlers.register("growth_propose@v1", lambda payload, effects, env: _growth_propose(payload, effects, env, event_store=event_store, llm=marketing_llm))
    handlers.register("growth_strategy_generate@v1", lambda payload, effects, env: _growth_generate(payload, effects, env, event_store=event_store, llm=marketing_llm))
    handlers.register("growth_strategy_backlog@v1", lambda payload, effects, env: _growth_backlog(payload, effects, env, event_store=event_store))
    handlers.register("growth_strategy_accept@v1", lambda payload, effects, env: _growth_accept(payload, effects, env, event_store=event_store))
    handlers.register("growth_strategy_reject@v1", lambda payload, effects, env: _growth_reject(payload, effects, env, event_store=event_store))

    handlers.register(
        "track_event@v1",
        lambda payload, effects, env: effects.track_event(
            decision_id=env.decision.decision_id,
            correlation_id=env.decision.correlation_id,
            user_id=payload["user_id"],
            event_type=str(payload.get("event_type") or ""),
            payload=(payload.get("payload") if isinstance(payload.get("payload"), dict) else None),
            source=str(payload.get("source") or "tracking"),
        ),
    )
    handlers.register(
        "emit_event@v1",
        lambda payload, effects, env: effects.track_event(
            decision_id=env.decision.decision_id,
            correlation_id=env.decision.correlation_id,
            user_id=payload["user_id"],
            event_type=str(payload.get("event_type") or ""),
            payload=(payload.get("payload") if isinstance(payload.get("payload"), dict) else None),
            source=str(payload.get("source") or "executor"),
        ),
    )

    handlers.register("behavior_graph_build@v1", lambda payload, effects, env: handle_behavior_graph_build(payload, effects, env, event_store=event_store, store=behavior_graph_store))
    handlers.register("behavior_graph_neighbors@v1", lambda payload, effects, env: handle_behavior_graph_neighbors(payload, effects, env, store=behavior_graph_store))
    handlers.register("behavior_graph_path@v1", lambda payload, effects, env: handle_behavior_graph_path(payload, effects, env, store=behavior_graph_store))
    handlers.register("behavior_graph_node@v1", lambda payload, effects, env: handle_behavior_graph_node(payload, effects, env, store=behavior_graph_store))
    handlers.register("behavior_graph_reset@v1", lambda payload, effects, env: handle_behavior_graph_reset(payload, effects, env, store=behavior_graph_store))

from __future__ import annotations

from runtime.actions import ACTION_ADS_APPLY_EXECUTE_V1
from runtime.handlers import ActionHandlerRegistry
from runtime.handlers.ads_apply_evidence import attach_ads_apply_outcome
from runtime.handlers.delivery_contract import delivery_kwargs

CANON_BOOT_WIRING_ONLY = True


def register_ads_handlers(*, handlers: ActionHandlerRegistry, event_store, ads_runtime, ads_autopilot_engine, ads_apply_engine) -> None:
    from runtime.handlers.ads_apply_execute import handle_ads_apply_execute as _ads_apply_execute
    from runtime.handlers.ads_autopilot_tick import handle_ads_autopilot_tick
    from runtime.handlers.ads_rl_report import handle_ads_rl_report
    from runtime.handlers.ads_rl_suggest import handle_ads_rl_suggest
    from runtime.handlers.ads_rl_train_tick import handle_ads_rl_train_tick
    from runtime.handlers.reward_observe import handle_reward_observe

    handlers.register("ads_rl_suggest@v1", lambda payload, effects, env: handle_ads_rl_suggest(payload, effects, env, event_store=event_store))
    handlers.register("ads_rl_train_tick@v1", lambda payload, effects, env: handle_ads_rl_train_tick(payload, effects, env, event_store=event_store))
    handlers.register("ads_rl_report@v1", lambda payload, effects, env: handle_ads_rl_report(payload, effects, env, event_store=event_store))
    handlers.register("reward_observe@v1", lambda payload, effects, env: handle_reward_observe(payload, effects, env, event_store=event_store))

    handlers.register(
        "ads_autopilot_tick@v1",
        lambda payload, effects, env: handle_ads_autopilot_tick(
            payload,
            effects,
            env,
            engine=ads_autopilot_engine,
            event_store=event_store,
        ),
    )

    def _ads_apply_exec(payload, effects, env):
        if ads_runtime is None:
            notification = effects.send_message(
                decision_id=env.decision.decision_id,
                correlation_id=env.decision.correlation_id,
                tenant_id=str((payload or {}).get("tenant_id") or "").strip(),
                user_id=str((payload or {}).get("user_id") or "unknown"),
                text="Ads runtime не настроен. Проверь конфиг connectors/OAuth.",
                reply_markup={"inline_keyboard": [[{"text": "⬅️ Назад", "callback_data": "ads:apply:menu"}]]},
                callback_query_id=(payload or {}).get("callback_query_id"),
                critical=False,
                **delivery_kwargs(payload or {}),
            )
            return attach_ads_apply_outcome(
                notification=notification,
                status="blocked",
                detail={"reason": "ads_runtime_not_configured"},
            )
        return _ads_apply_execute(payload, effects, env, engine=ads_apply_engine, event_store=event_store)

    handlers.register(ACTION_ADS_APPLY_EXECUTE_V1, _ads_apply_exec)

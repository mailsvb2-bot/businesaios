"""Canonical runtime action catalog data.

Single source of truth for runtime action rows and registry grouping metadata.
This module intentionally stores only declarative action metadata so boot wiring
and the public actions registry do not each grow their own competing tables.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

CANON_BOOT_WIRING_ONLY = True
SPEC_ROWS: tuple[tuple[str, str, bool, str, int, int], ...] = (
    ("admin_set_perm@v1", "runtime.handlers_ops:handle_admin_set_perm", True, "admin", 60, 60),
    ("admin_set_role@v1", "runtime.handlers_ops:handle_admin_set_role", True, "admin", 60, 60),
    ("admin_user_card@v1", "runtime.handlers_ops:handle_admin_user_card", True, "admin", 60, 60),
    ("ads_apply_execute@v1", "runtime.handlers.ads_apply_execute:handle_ads_apply_execute", True, "ads", 30, 30),
    ("ads_rl_suggest@v1", "runtime.handlers.ads_rl_suggest:handle_ads_rl_suggest", True, "ads", 30, 30),
    ("ads_rl_train_tick@v1", "runtime.handlers.ads_rl_train_tick:handle_ads_rl_train_tick", True, "ads", 30, 30),
    ("ads_rl_report@v1", "runtime.handlers.ads_rl_report:handle_ads_rl_report", True, "ads", 60, 60),
    ("ads_autopilot_tick@v1", "runtime.handlers.ads_autopilot_tick:handle_ads_autopilot_tick", True, "ads", 30, 30),
    ("ai_ceo_plan@v1", "runtime.handlers.ai_ceo_plan:handle_ai_ceo_plan", True, "llm", 60, 30),
    ("autopilot_decision@v1", "runtime.boot.system_builder:inline", True, "general", 120, 60),
    ("autopilot_run_started@v1", "runtime.boot.system_builder:inline", True, "general", 120, 60),
    ("autopilot_started@v1", "runtime.boot.system_builder:inline", True, "general", 120, 60),
    ("pricing_select@v1", "runtime.handlers.pricing_select:handle_pricing_select", True, "general", 60, 30),
    ("reward_observe@v1", "runtime.handlers.reward_observe:handle_reward_observe", True, "general", 120, 60),
    ("growth_propose@v1", "runtime.handlers.growth_propose:handle_growth_propose", True, "general", 60, 30),
    ("answer_callback@v1", "runtime.handlers_ops:handle_answer_callback", True, "general", 120, 60),
    ("apply_pricing_change@v1", "runtime.handlers_ops:handle_apply_pricing_change", True, "general", 120, 60),
    ("behavior_graph_build@v1", "runtime.handlers.behavior_graph:handle_behavior_graph_build", True, "general", 30, 30),
    ("behavior_graph_neighbors@v1", "runtime.handlers.behavior_graph:handle_behavior_graph_neighbors", True, "general", 120, 60),
    ("behavior_graph_node@v1", "runtime.handlers.behavior_graph:handle_behavior_graph_node", True, "general", 120, 60),
    ("behavior_graph_path@v1", "runtime.handlers.behavior_graph:handle_behavior_graph_path", True, "general", 120, 60),
    ("behavior_graph_reset@v1", "runtime.handlers.behavior_graph:handle_behavior_graph_reset", True, "general", 30, 30),
    ("capture_payment@v1", "runtime.handlers_ops:handle_capture_payment", True, "payments", 60, 30),
    ("create_payment_and_send_link@v1", "runtime.handlers_ops:handle_create_payment_and_send_link", True, "payments", 60, 30),
    ("deploy_policy@v1", "runtime.handlers_ops:handle_deploy_policy", True, "general", 120, 60),
    ("emit_event@v1", "runtime.boot.system_builder:inline", True, "general", 120, 60),
    ("grant_access@v1", "runtime.handlers_ops:handle_grant_access", True, "payments", 60, 30),
    ("log_mood@v1", "runtime.handlers_ops:handle_log_mood", True, "general", 120, 60),
    ("noop@v1", "runtime.handlers_messaging:handle_noop", False, "none", 999999, 999999),
    ("one_click_value@v1", "runtime.handlers_messaging:handle_one_click_value", True, "llm", 60, 30),
    ("poll_telegram_updates@v1", "runtime.handlers_messaging:handle_poll_telegram_updates", False, "general", 120, 60),
    ("profit_sprint_onboarding_lead_source@v1", "runtime.boot.system_builder:inline", True, "general", 120, 60),
    ("profit_sprint_onboarding_start@v1", "runtime.boot.system_builder:inline", True, "general", 120, 60),
    ("profit_sprint_onboarding_text@v1", "runtime.boot.system_builder:inline", True, "general", 120, 60),
    ("reconcile_payment@v1", "runtime.handlers_ops:handle_reconcile_payment", True, "payments", 60, 30),
    ("reconcile_payments@v1", "runtime.handlers_ops:handle_reconcile_payments", True, "payments", 60, 30),
    ("reject_pricing_change@v1", "runtime.handlers_ops:handle_reject_pricing_change", True, "general", 120, 60),
    ("request_pricing_change@v1", "runtime.handlers_ops:handle_request_pricing_change", True, "general", 120, 60),
    ("rollback_policy@v1", "runtime.handlers_ops:handle_rollback_policy", True, "general", 120, 60),
    ("select_tariff@v1", "runtime.handlers_ops:handle_select_tariff", True, "payments", 60, 30),
    ("send_audio@v1", "runtime.handlers_ops:handle_send_audio", True, "general", 120, 60),
    ("send_marketing_offer@v1", "runtime.handlers_messaging:handle_send_marketing_offer", True, "llm", 60, 30),
    ("send_message@v1", "runtime.handlers_messaging:handle_send_message", True, "general", 120, 60),
    ("send_weather@v1", "runtime.handlers_ops:handle_send_weather", True, "general", 120, 60),
    ("set_marketing_copy@v1", "runtime.handlers_ops:handle_set_marketing_copy", True, "llm", 60, 30),
    ("set_user_setting@v1", "runtime.handlers_ops:handle_set_user_setting", True, "general", 120, 60),
    ("telegram_self_check@v1", "runtime.handlers_messaging:handle_telegram_self_check", False, "general", 120, 60),
    ("track_event@v1", "runtime.boot.system_builder:inline", True, "general", 120, 60),
    ("growth_strategy_generate@v1", "runtime.handlers.growth_strategy_generate:handle_growth_strategy_generate", True, "llm", 30, 15),
    ("growth_strategy_backlog@v1", "runtime.handlers.growth_strategy_backlog:handle_growth_strategy_backlog", True, "general", 120, 60),
    ("growth_strategy_accept@v1", "runtime.handlers.growth_strategy_state:handle_growth_strategy_accept", True, "general", 120, 60),
    ("growth_strategy_reject@v1", "runtime.handlers.growth_strategy_state:handle_growth_strategy_reject", True, "general", 120, 60),
    ("execute_plan@v1", "runtime.handlers:ActionHandlerRegistry.handle", True, "general", 120, 60),
    ("enqueue_evolution_job@v1", "runtime.effects.registry:build_effects_registry", True, "general", 60, 30),
    ("apply_offer_patch@v1", "runtime.effects.registry:build_effects_registry", True, "general", 60, 30),
    ("suggest_offer_patch@v1", "runtime.effects.registry:build_effects_registry", True, "general", 60, 30),
)
INLINE_ALLOWLIST_NAMES: tuple[str, ...] = (
    "emit_event@v1",
    "track_event@v1",
    "autopilot_decision@v1",
    "autopilot_run_started@v1",
    "autopilot_started@v1",
    "profit_sprint_onboarding_lead_source@v1",
    "profit_sprint_onboarding_start@v1",
    "profit_sprint_onboarding_text@v1",
    "growth_strategy_generate@v1",
    "growth_strategy_backlog@v1",
    "growth_strategy_accept@v1",
    "growth_strategy_reject@v1",
    "execute_plan@v1",
    "enqueue_evolution_job@v1",
    "apply_offer_patch@v1",
    "suggest_offer_patch@v1",
)

BUILTIN_HANDLER_ACTIONS: frozenset[str] = frozenset({"execute_plan@v1"})
EFFECT_ONLY_ACTIONS: frozenset[str] = frozenset({
    "enqueue_evolution_job@v1",
    "apply_offer_patch@v1",
    "suggest_offer_patch@v1",
})

# Verification semantics belong to the canonical action catalog. They describe
# already-issued actions and never select or alter a DecisionCore action.
EXTERNAL_EFFECT_ACTIONS: frozenset[str] = frozenset(
    {
        "ads_apply_execute@v1",
        "answer_callback@v1",
        "capture_payment@v1",
        "create_payment_and_send_link@v1",
        "one_click_value@v1",
        "send_audio@v1",
        "send_marketing_offer@v1",
        "send_message@v1",
        "send_weather@v1",
    }
)
ADVISORY_ACTIONS: frozenset[str] = frozenset(
    {
        "admin_user_card@v1",
        "ads_rl_suggest@v1",
        "ads_rl_report@v1",
        "ai_ceo_plan@v1",
        "behavior_graph_neighbors@v1",
        "behavior_graph_node@v1",
        "behavior_graph_path@v1",
        "growth_propose@v1",
        "growth_strategy_backlog@v1",
        "growth_strategy_generate@v1",
        "poll_telegram_updates@v1",
        "pricing_select@v1",
        "suggest_offer_patch@v1",
        "telegram_self_check@v1",
    }
)


def execution_category_for_action(action: str) -> str:
    name = str(action)
    if name in EXTERNAL_EFFECT_ACTIONS:
        return "external_effect"
    if name in ADVISORY_ACTIONS:
        return "advisory"
    return "internal_bookkeeping"


def external_confirmation_mode_for_action(action: str) -> str:
    return "required" if str(action) in EXTERNAL_EFFECT_ACTIONS else "not_required"


def build_specs_registry(*, rows: Iterable[Sequence[str | int | bool]], spec_factory, registry_type):
    registry = {}
    for row in rows:
        name, handler_ref, idem, kind, pt, pu = row
        registry[str(name)] = spec_factory(
            str(name),
            str(handler_ref),
            idem=bool(idem),
            kind=kind,
            pt=int(pt),
            pu=int(pu),
        )
    return registry_type(registry)


def build_inline_allowlist(*, names: Iterable[str]) -> set[str]:
    return {str(name) for name in names}


def handler_actions_from(all_actions: Iterable[str]) -> set[str]:
    return {str(name) for name in all_actions if str(name) not in EFFECT_ONLY_ACTIONS}


__all__ = [
    "ADVISORY_ACTIONS",
    "BUILTIN_HANDLER_ACTIONS",
    "EFFECT_ONLY_ACTIONS",
    "EXTERNAL_EFFECT_ACTIONS",
    "INLINE_ALLOWLIST_NAMES",
    "SPEC_ROWS",
    "build_inline_allowlist",
    "build_specs_registry",
    "execution_category_for_action",
    "external_confirmation_mode_for_action",
    "handler_actions_from",
]

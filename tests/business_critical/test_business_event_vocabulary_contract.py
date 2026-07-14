from __future__ import annotations

import pytest

from core.events.event_types import is_known, normalize_event_type


BUSINESS_PLATFORM_EVENTS = (
    "admin_notification_failed",
    "admin_notification_sent",
    "admin_perm_set",
    "admin_pricing_change_applied",
    "admin_pricing_change_rejected",
    "admin_pricing_change_requested",
    "admin_role_set",
    "admin_user_card@v1",
    "admin_user_card_failed@v1",
    "ads_apply_audit_emit_failed@v1",
    "ads_apply_decision_executed_emit_failed@v1",
    "ads_apply_execute_blocked@v1",
    "ads_apply_executed@v1",
    "ads_apply_maturity_mark_failed@v1",
    "ads_autopilot_error@v1",
    "ads_autopilot_tick@v1",
    "ads_autopilot_tick_blocked@v1",
    "ads_rl_suggestion@v1",
    "ads_rl_suggest_blocked@v1",
    "ads_rl_suggest_ok@v1",
    "ads_rl_suggest_skipped@v1",
    "ads_rl_train_ok@v1",
    "ads_rl_train_report@v1",
    "ads_rl_train_skipped@v1",
    "ai_ceo_plan@v1",
    "ai_ceo_plan_blocked@v1",
    "ai_ceo_plan_error@v1",
    "autopilot_decision",
    "autopilot_run_started",
    "autopilot_started",
    "entitlement_granted",
    "evolution_job_enqueued",
    "growth_experiment_created@v1",
    "growth_hypothesis_created@v1",
    "growth_hypothesis_scored@v1",
    "growth_hypothesis_state@v1",
    "growth_strategy_accept@v1",
    "growth_strategy_backlog@v1",
    "growth_strategy_generate@v1",
    "growth_strategy_generated@v1",
    "growth_strategy_plan_manifest@v1",
    "growth_strategy_reject@v1",
    "growth_strategy_snapshot@v1",
    "marketing_copy_set",
    "messaging_effect_warning",
    "offer_patch_applied@v1",
    "offer_patch_rolled_back@v1",
    "policy_deployed",
    "policy_rolled_back",
    "pricing_select@v1",
    "pricing_select_blocked@v1",
    "product_selected@v1",
    "profit_sprint_onboarding_lead_source@v1",
    "profit_sprint_onboarding_start@v1",
    "profit_sprint_onboarding_text@v1",
    "tariff_selected",
    "user_setting_set",
    "variant_chosen",
    "variant_shown",
    "weather_sent",
)


@pytest.mark.lock
def test_strict_event_vocabulary_contains_real_business_runtime_events() -> None:
    unknown = [event_type for event_type in BUSINESS_PLATFORM_EVENTS if not is_known(event_type)]

    assert unknown == []


@pytest.mark.lock
def test_legacy_access_granted_normalizes_to_canonical_entitlement_event() -> None:
    assert normalize_event_type("access_granted") == "entitlement_granted"
    assert is_known("access_granted") is True


@pytest.mark.lock
def test_preserved_audio_mood_and_gift_events_are_known_platform_events() -> None:
    for event_type in (
        "audio_sent",
        "audio_started",
        "audio_progress",
        "audio_stopped",
        "audio_completed",
        "mood_logged",
        "gift_token_created",
        "gift_redeemed",
        "gift_redeem_failed",
        "reward_observe@v1",
        "reward_observe_blocked@v1",
        "growth_propose@v1",
        "growth_propose_blocked@v1",
    ):
        assert is_known(event_type) is True

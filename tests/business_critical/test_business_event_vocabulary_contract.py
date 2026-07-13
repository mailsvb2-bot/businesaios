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
    "autopilot_decision",
    "autopilot_run_started",
    "autopilot_started",
    "entitlement_granted",
    "growth_experiment_created@v1",
    "growth_hypothesis_created@v1",
    "growth_hypothesis_scored@v1",
    "growth_hypothesis_state@v1",
    "growth_strategy_generated@v1",
    "growth_strategy_snapshot@v1",
    "marketing_copy_set",
    "messaging_effect_warning",
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
def test_consumer_audio_and_mood_events_are_not_known_platform_events() -> None:
    for event_type in (
        "audio_sent",
        "audio_started",
        "audio_progress",
        "audio_stopped",
        "audio_completed",
        "mood_logged",
    ):
        assert is_known(event_type) is False

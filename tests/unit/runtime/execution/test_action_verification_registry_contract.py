from __future__ import annotations

from runtime.boot.actions_catalog import (
    BEST_EFFORT_EXTERNAL_ACTIONS,
    CONDITIONAL_EXTERNAL_EFFECT_ACTIONS,
    EXTERNAL_EFFECT_ACTIONS,
)
from runtime.boot.actions_registry import SPECS, get_spec


def test_every_registered_action_has_closed_verification_contract() -> None:
    allowed_categories = {
        "external_effect",
        "external_best_effort",
        "internal_bookkeeping",
        "advisory",
    }
    allowed_modes = {"required", "conditional", "not_required"}

    assert SPECS
    for spec in SPECS:
        assert spec.execution_category in allowed_categories
        assert spec.external_confirmation_mode in allowed_modes


def test_required_external_actions_are_owned_by_canonical_registry() -> None:
    required = {
        spec.name
        for spec in SPECS
        if spec.external_confirmation_mode == "required"
    }

    assert required == set(EXTERNAL_EFFECT_ACTIONS)
    assert all(get_spec(name).execution_category == "external_effect" for name in required)


def test_ads_apply_is_the_only_conditional_external_action() -> None:
    conditional = {
        spec.name
        for spec in SPECS
        if spec.external_confirmation_mode == "conditional"
    }

    assert conditional == set(CONDITIONAL_EXTERNAL_EFFECT_ACTIONS)
    assert conditional == {"ads_apply_execute@v1"}


def test_best_effort_external_actions_cannot_silently_become_required() -> None:
    best_effort = {
        spec.name
        for spec in SPECS
        if spec.execution_category == "external_best_effort"
    }

    assert best_effort == set(BEST_EFFORT_EXTERNAL_ACTIONS)
    assert best_effort == {"answer_callback@v1"}
    assert all(get_spec(name).external_confirmation_mode == "not_required" for name in best_effort)


def test_business_critical_effects_require_observable_confirmation() -> None:
    for action in (
        "admin_set_perm@v1",
        "admin_set_role@v1",
        "admin_user_card@v1",
        "ads_rl_suggest@v1",
        "ai_ceo_plan@v1",
        "apply_pricing_change@v1",
        "capture_payment@v1",
        "create_payment_and_send_link@v1",
        "deploy_policy@v1",
        "grant_access@v1",
        "growth_strategy_accept@v1",
        "growth_strategy_backlog@v1",
        "growth_strategy_generate@v1",
        "growth_strategy_reject@v1",
        "pricing_select@v1",
        "profit_sprint_onboarding_lead_source@v1",
        "profit_sprint_onboarding_start@v1",
        "profit_sprint_onboarding_text@v1",
        "reject_pricing_change@v1",
        "request_pricing_change@v1",
        "rollback_policy@v1",
        "select_tariff@v1",
        "send_marketing_offer@v1",
        "send_message@v1",
        "send_weather@v1",
        "set_marketing_copy@v1",
        "set_user_setting@v1",
    ):
        spec = get_spec(action)
        assert spec.execution_category == "external_effect"
        assert spec.external_confirmation_mode == "required"


def test_consumer_and_unwired_ghost_actions_are_not_registered() -> None:
    for action in (
        "send_audio@v1",
        "log_mood@v1",
        "reward_observe@v1",
        "growth_propose@v1",
    ):
        assert action not in SPECS

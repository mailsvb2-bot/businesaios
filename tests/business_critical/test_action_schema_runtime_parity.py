from __future__ import annotations

import inspect

import pytest

from core.actions.catalog import build_catalog
from runtime._internal.effects_domains.admin_state import AdminStateEffectsMixin
from runtime.boot.actions_registry import all_actions, get_spec
from runtime.ports.effects_admin import EffectsAdminPort
from runtime.ports.effects_platform import EffectsPlatformPort


@pytest.mark.lock
def test_decision_schema_catalog_has_exact_runtime_action_name_parity() -> None:
    catalog = build_catalog()

    assert set(catalog) == all_actions()
    assert {
        "send_audio@v1",
        "log_mood@v1",
        "reward_observe@v1",
        "growth_propose@v1",
    }.issubset(catalog)


@pytest.mark.lock
def test_every_confirmed_external_action_has_an_explicit_closed_schema() -> None:
    catalog = build_catalog()
    offenders: list[str] = []

    for action in sorted(all_actions()):
        spec = get_spec(action)
        if spec.external_confirmation_mode not in {"required", "conditional"}:
            continue
        schema = catalog[action].schema
        if schema.allow_additional:
            offenders.append(action)

    assert offenders == [], "high-risk actions using permissive compatibility schemas: " + ", ".join(offenders)


@pytest.mark.lock
def test_business_scope_is_required_by_external_tenant_owned_schemas() -> None:
    catalog = build_catalog()
    for action in (
        "admin_set_perm@v1",
        "admin_set_role@v1",
        "admin_user_card@v1",
        "ads_apply_execute@v1",
        "ads_rl_suggest@v1",
        "ai_ceo_plan@v1",
        "apply_offer_patch@v1",
        "apply_pricing_change@v1",
        "capture_payment@v1",
        "create_payment_and_send_link@v1",
        "deploy_policy@v1",
        "enqueue_evolution_job@v1",
        "grant_access@v1",
        "growth_propose@v1",
        "log_mood@v1",
        "growth_strategy_accept@v1",
        "growth_strategy_backlog@v1",
        "growth_strategy_generate@v1",
        "growth_strategy_reject@v1",
        "one_click_value@v1",
        "pricing_select@v1",
        "reward_observe@v1",
        "profit_sprint_onboarding_lead_source@v1",
        "profit_sprint_onboarding_start@v1",
        "profit_sprint_onboarding_text@v1",
        "reject_pricing_change@v1",
        "request_pricing_change@v1",
        "rollback_policy@v1",
        "select_tariff@v1",
        "send_audio@v1",
        "send_marketing_offer@v1",
        "send_message@v1",
        "send_weather@v1",
        "set_marketing_copy@v1",
        "set_user_setting@v1",
        "suggest_offer_patch@v1",
    ):
        assert "tenant_id" in catalog[action].schema.required, action


@pytest.mark.lock
def test_pricing_apply_cannot_bypass_immutable_request_governance() -> None:
    catalog = build_catalog()
    schema = catalog["apply_pricing_change@v1"].schema

    assert "request_id" in schema.required
    assert "requested_by" not in schema.required
    assert "requested_by" not in schema.optional
    assert "requested_by" not in schema.field_types

    mixin_parameters = inspect.signature(
        AdminStateEffectsMixin.apply_pricing_change
    ).parameters
    port_parameters = inspect.signature(
        EffectsAdminPort.apply_pricing_change
    ).parameters
    for parameters in (mixin_parameters, port_parameters):
        assert "request_id" in parameters
        assert parameters["request_id"].default is inspect.Signature.empty
        assert "requested_by" not in parameters


@pytest.mark.lock
def test_payment_actions_require_complete_tenant_product_order_causality() -> None:
    catalog = build_catalog()
    expected = {
        "tenant_id",
        "product_id",
        "order_id",
        "user_id",
        "amount",
        "currency",
    }
    for action in (
        "capture_payment@v1",
        "create_payment_and_send_link@v1",
    ):
        schema = catalog[action].schema
        assert expected.issubset(schema.required), action
        assert {"product_id", "order_id"}.isdisjoint(schema.optional), action


@pytest.mark.lock
def test_platform_effect_ports_require_canonical_route_and_tenant_identity() -> None:
    for method_name in (
        "enqueue_evolution_job",
        "suggest_offer_patch",
        "apply_offer_patch",
    ):
        parameters = inspect.signature(
            getattr(EffectsPlatformPort, method_name)
        ).parameters
        for field in ("decision_id", "correlation_id", "tenant_id"):
            assert field in parameters, f"{method_name}:{field}"
            assert parameters[field].default is inspect.Signature.empty


@pytest.mark.lock
def test_product_scoped_admin_views_and_rejections_are_schema_valid() -> None:
    catalog = build_catalog()

    assert "product_id" in catalog["admin_user_card@v1"].schema.optional
    assert "product_id" in catalog["reject_pricing_change@v1"].schema.optional

from __future__ import annotations

import pytest

from core.actions.catalog import build_catalog
from runtime.boot.actions_registry import all_actions, get_spec


FORBIDDEN_ACTIONS = {
    "send_audio@v1",
    "log_mood@v1",
    "reward_observe@v1",
    "growth_propose@v1",
}


@pytest.mark.lock
def test_decision_schema_catalog_has_exact_runtime_action_name_parity() -> None:
    catalog = build_catalog()

    assert set(catalog) == all_actions()
    assert FORBIDDEN_ACTIONS.isdisjoint(catalog)


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
        "apply_pricing_change@v1",
        "capture_payment@v1",
        "create_payment_and_send_link@v1",
        "grant_access@v1",
        "one_click_value@v1",
        "pricing_select@v1",
        "request_pricing_change@v1",
        "select_tariff@v1",
        "send_marketing_offer@v1",
        "send_message@v1",
        "send_weather@v1",
        "set_marketing_copy@v1",
        "set_user_setting@v1",
    ):
        assert "tenant_id" in catalog[action].schema.required, action

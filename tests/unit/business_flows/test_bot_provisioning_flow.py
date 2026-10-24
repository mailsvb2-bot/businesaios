from __future__ import annotations

from types import SimpleNamespace

import pytest

from application.business_flows import bot_provisioning as bp
from core.policies.telegram.routes.business_flow_routes import handle_business_flow_routes
from core.safety.operational.action_registry import build_default_operational_action_registry
from runtime.handler_impl.domains.bot_provisioning_ops import handle_bot_provisioning


def test_request_status_cancel_roundtrip_through_event_store(flow) -> None:
    out, text = flow.run(handle_bot_provisioning, op="request", arg="@Shop_Helper_bot")
    assert out["ok"] and "@shop_helper_bot" in text
    _, text = flow.run(handle_bot_provisioning, op="request", arg="other_bot")
    assert "already_active" in text
    _, text = flow.run(handle_bot_provisioning, op="status")
    assert "ожидает токен" in text
    _, text = flow.run(handle_bot_provisioning, op="cancel")
    assert "отменено" in text
    _, text = flow.run(handle_bot_provisioning, op="status")
    assert "Активных подключений нет" in text
    assert [e["payload"]["step"] for e in flow.store.events] == ["requested", "cancel"]


def test_state_machine_requires_credential_reference_never_raw_token() -> None:
    item = bp.Provisioning("r1", "shop_bot", bp.ProvisioningStatus.AWAITING_SECRET)
    with pytest.raises(ValueError, match="credential_reference"):
        bp.transition(item, "secret_attached", credential_ref="123456:AAE-raw-token")
    ready = bp.transition(item, "secret_attached", credential_ref="vault:bots/shop")
    verifying = bp.transition(bp.Provisioning("r1", "shop_bot", bp.ProvisioningStatus.READY), "verify_started")
    state = bp.replay([{"request_id": "r1", "step": "requested", "username": "shop_bot"}, ready, verifying])
    assert state["r1"].status is bp.ProvisioningStatus.VERIFYING
    with pytest.raises(ValueError, match="invalid_transition"):
        bp.transition(state["r1"], "retry")


@pytest.mark.parametrize("name", ["ab", "shop", "x" * 40 + "bot", "bad-name_bot"])
def test_invalid_usernames_rejected(name) -> None:
    with pytest.raises(ValueError):
        bp.normalize_username(name)


def test_route_is_owner_only_and_action_needs_no_human_approval() -> None:
    ctx = SimpleNamespace(cmd="/connect_bot", args=" shop_bot ", is_admin=False)
    assert handle_business_flow_routes(ctx, user_id="u1") is None
    proposed = handle_business_flow_routes(
        SimpleNamespace(cmd="/connect_bot", args="shop_bot", is_admin=True), user_id="u1"
    )
    assert proposed is not None
    spec = build_default_operational_action_registry().get("bot_provisioning@v1")
    assert spec is not None and not spec.requires_human_approval

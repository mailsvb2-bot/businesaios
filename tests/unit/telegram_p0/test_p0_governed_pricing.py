"""P0 governed pricing: product scope, deterministic request and closed schema."""
from __future__ import annotations

from core.actions.catalog_groups import governance_catalog
from core.ai.world_state import WorldStateV1
from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.handlers.admin.pricing import handle_pricing
from core.policies.telegram.handlers.admin.pricing_support import pricing_request_id
from core.policies.telegram.handlers.admin_pricing import handle_admin_pricing_session


def _ctx(*, callback: str = "", text: str = "", settings=None, product=None):
    state = WorldStateV1(
        schema_version=1, user={}, session={}, economy={},
        product=product if product is not None else {"product_id": "prod-a", "business_id": "biz-a"},
        timestamp_ms=123, tenant_id="tenant-test", user_id="4001",
    )
    return TelegramCtx(
        state=state, text=text, cmd=None, args="", callback_data=callback,
        callback_query_id="callback-001", settings=settings or {}, city="", moods=[],
        admin_metrics={}, is_admin=True, roles=["admin"], perms=[], is_superadmin=True,
        realtime_state={}, pricing_suggestions={"2": 2600}, full_access=False,
        pay_status="none", selected_tariff={}, marketing_variants={},
        marketing_seed="1", marketing_bandit={},
    )


def test_pricing_scope_does_not_read_unbound_product_or_global_catalog(monkeypatch):
    called = []
    def catalog(*, tenant_id, product_id):
        called.append((tenant_id, product_id))
        return [{"plan_id": 2, "price": 2400, "title": "Plan"}]
    monkeypatch.setattr("core.plans.active_plans", catalog)
    blocked = handle_pricing(_ctx(callback="admin:pricing:edit:2", product={}),
                             pm=lambda **kwargs: kwargs)
    assert "Тариф не найден" in blocked["text"]
    assert called == []
    ctx = _ctx(callback="admin:pricing:edit:2")
    result = handle_pricing(ctx, pm=lambda **kwargs: kwargs)
    assert result.action == "set_user_setting@v1"
    assert result.payload["value"]["plan_id"] == 2
    assert result.payload["value"]["nonce"] == "callback-001"
    assert called == [("tenant-test", "prod-a")]


def test_ai_hint_uses_bound_read_model_not_event_store(monkeypatch):
    monkeypatch.setattr("core.plans.active_plans",
                        lambda *, tenant_id, product_id: [{"plan_id": 2, "price": 2400, "title": "Plan"}])
    ctx = _ctx(callback="admin:pricing:ai:2")
    result = handle_pricing(ctx, pm=lambda **kwargs: kwargs)
    assert "Рекомендуемая: 2600" in result["text"]


def test_pricing_request_id_is_stable_per_update_and_unique_per_new_press():
    kwargs = dict(admin_id="4001", plan_id=2, new_price=2600)
    first = pricing_request_id(**kwargs, nonce="callback-001")
    assert first == pricing_request_id(**kwargs, nonce="callback-001")
    assert first != pricing_request_id(**kwargs, nonce="callback-002")


def test_price_session_emits_schema_valid_request_for_same_admin(monkeypatch):
    monkeypatch.setattr("core.plans.active_plans",
                        lambda *, tenant_id, product_id: [{"plan_id": 2, "price": 2400, "title": "Plan"}])
    ctx = _ctx(text="2600", settings={"admin:pricing_session":
                              {"stage": "await_price", "plan_id": 2, "nonce": "callback-001"}})
    result = handle_admin_pricing_session(ctx, user_id="4001",
                                           pm=lambda *args: {"text": args[0]})
    assert result.action == "request_pricing_change@v1"
    payload = result.payload
    schema = governance_catalog()["request_pricing_change@v1"].schema
    assert set(payload) <= schema.required | schema.optional
    assert payload["request_id"] == pricing_request_id(
        admin_id="4001", plan_id=2, new_price=2600, nonce="callback-001")
    assert payload["admin_id"] == "4001"
    assert "user_id" not in payload
    assert "requested_by" not in payload

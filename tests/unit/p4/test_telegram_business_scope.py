from types import SimpleNamespace

from core.policies.telegram.context import trusted_sales_business_scope


def test_business_scope_only_uses_world_state():
    ctx = SimpleNamespace(
        state=SimpleNamespace(tenant_id="t1", product={"product_id": "product1", "business_id": "b1"}),
        text="business_id=b2", args="b2", settings={"sales:business": {"business_id": "b2"}},
    )
    assert trusted_sales_business_scope(ctx) == {"business_id": "b1"}


def test_unverified_sales_scope_stays_missing():
    ctx = SimpleNamespace(state=SimpleNamespace(tenant_id="t1", product={}), text="b2",
                          settings={"sales:business": {"business_id": "b2"}})
    assert trusted_sales_business_scope(ctx, owner=False) == {}
    assert trusted_sales_business_scope(ctx) == {"business_id": "b2"}


def test_customer_never_uses_owner_choice():
    ctx = SimpleNamespace(state=SimpleNamespace(tenant_id="t1", product={}), text="hi",
                          settings={"sales:business": {"business_id": "b2"}})
    assert trusted_sales_business_scope(ctx, owner=False) == {}

def test_executor_business_picker_validates_canonical_organizations(monkeypatch):
    from runtime.handler_impl.domains.business_flow_ops import handle_sales_pipeline
    from tests.unit.business_flows.conftest import FlowEffects, FlowStore

    monkeypatch.setenv("BAI_SALES_BUSINESS_SCOPE_REQUIRED", "1")
    monkeypatch.setattr("application.organization.registry.active_businesses",
                        lambda event_store, tenant_id: {"biz-a": "Клиника", "biz-b": "Школа"})
    store = FlowStore()
    class Effects(FlowEffects):
        def __init__(self, store):
            super().__init__(store)
            self.settings = []
        def set_user_setting(self, **kw):
            self.settings.append(kw)

    effects = Effects(store)
    env = SimpleNamespace(decision=SimpleNamespace(decision_id="d1", correlation_id="c1"))

    def run(op, arg="", business_id=""):
        return handle_sales_pipeline(
            {"tenant_id": "t1", "user_id": "u1", "business_id": business_id, "op": op, "arg": arg},
            effects, env, event_store=store, now_ms=1_700_000_000_000)

    run("business_pick")
    assert "Школа" in effects.sent[-1]["reply_markup"]["inline_keyboard"][1][0]["text"]
    assert not effects.settings
    run("business_select", "foreign")
    assert not effects.settings
    run("business_select", "biz-b")
    assert effects.settings[-1]["value"] == {"business_id": "biz-b"}
    assert effects.settings[-1]["user_id"] == "u1"
    assert not store.events
    run("list", business_id="foreign")
    assert "Выберите бизнес" in effects.sent[-1]["text"]
    assert not store.events


def test_unscoped_customer_does_not_create_cross_business_lead(monkeypatch):
    from runtime.handler_impl.domains.business_flow_ops import handle_sales_pipeline
    from tests.unit.business_flows.conftest import FlowEffects, FlowStore

    monkeypatch.setenv("BAI_SALES_BUSINESS_SCOPE_REQUIRED", "1")
    monkeypatch.setattr("application.organization.registry.active_businesses",
                        lambda event_store, tenant_id: {"biz-a": "Клиника", "biz-b": "Школа"})
    store = FlowStore()
    effects = FlowEffects(store)
    env = SimpleNamespace(decision=SimpleNamespace(decision_id="d1", correlation_id="c1"))
    handle_sales_pipeline(
        {"tenant_id": "t1", "user_id": "customer", "op": "inbound", "arg": "hello",
         "reply": "Спасибо, сообщение получено."},
        effects, env, event_store=store, now_ms=1_700_000_000_000)
    assert not store.events

"""P1-18: Sales Center picks the canonical source among really connected CRMs and channels."""

from __future__ import annotations

from functools import partial
from pathlib import Path

import pytest

from application.business_autonomy.provider_truth_matrix import sales_source_provider_keys
from application.business_flows import cockpit_sales as sales_center
from runtime.handler_impl.domains.business_flow_ops import handle_sales_pipeline

LIVE = {"mode": "live", "accepted": True, "status": "live_executed"}


def _hist(op, count, at):
    return {**LIVE, "operation": op, "recorded_at_utc": at, "parsed_response": {"resource_count": count}}


def test_source_keys_come_from_the_truth_matrix():
    keys = sales_source_provider_keys()
    assert "hubspot" in keys["crm"] and {"telegram_bot", "vk_messaging", "max_messaging"} <= set(keys["channels"])


def test_crm_with_confirmed_reads_is_canonical_else_channels():
    hub = sales_center.crm_source(provider={"provider_key": "hubspot", "title": "HubSpot", "connected": True},
                                  history=[_hist("contact_sync", 12, "2026-11-01T10:00:00Z"),
                                           _hist("deal_sync", 5, "2026-11-01T10:01:00Z"),
                                           {**_hist("deal_sync", 99, "2026-11-02T00:00:00Z"), "accepted": False}])
    assert (hub["contacts"], hub["deals"], hub["read_confirmed"]) == (12, 5, True)
    chan = sales_center.channel_source(leads={"l1": type("L", (), {"source": "vk", "customer_id": "7"})()},
                                       last_fact_ms=1, connected_channels=["vk_messaging"])
    view = sales_center.choose([chan, hub])
    assert view["canonical_source"] == "hubspot" and view["selected_source"] == "hubspot"
    assert sales_center.choose([chan, hub], "channels")["selected_source"] == "channels"
    half = sales_center.crm_source(provider={"provider_key": "hubspot", "connected": True},
                                   history=[_hist("contact_sync", 3, "2026-11-01T10:00:00Z")])
    view = sales_center.choose([chan, half], "hubspot")  # unconfirmed CRM is never selected
    assert view["canonical_source"] == "channels" and view["selected_source"] == "channels"
    assert half["deals"] is None  # unknown stays unknown, not zero
    empty = sales_center.choose([sales_center.channel_source(leads={}, last_fact_ms=None, connected_channels=[])])
    assert empty["canonical_source"] is None and empty["write_actions_enabled"] is False


def test_handler_reads_the_canonical_pipeline_and_connected_providers(flow):
    import entrypoints.api.provider_admin_route_handlers as mod

    partial(flow.run, partial(handle_sales_pipeline, now_ms=1_800_000_000_000))(
        op="inbound", arg="Здравствуйте", reply="ok", user_id="cust7", business_id="b1")

    class H(mod.ProviderAdminRouteHandlers):
        def list_provider_catalog(self, *, tenant_id, business_id):
            return {"providers": [{"provider_key": "telegram_bot", "connected": True},
                                  {"provider_key": "hubspot", "title": "HubSpot", "connected": False}]}

        def list_provider_sync_history(self, **_):
            raise AssertionError("not connected -> no read")

    out = H(customer_event_store=flow.store).get_sales_sources(tenant_id="t1", business_id="b1")
    chan = out["sources"][0]
    assert chan["providers"] == ["telegram_bot"] and chan["deals"] == 1 and chan["contacts"] == 1
    assert out["canonical_source"] == "channels" and out["available"] == ["channels"]


@pytest.mark.parametrize("flag,code", [(None, 404), ("1", 200)])
def test_route_is_default_off(monkeypatch, flag, code):
    from fastapi import APIRouter, FastAPI
    from fastapi.testclient import TestClient

    import adapters.api.fastapi.business_workspace_provider_routes as routes

    monkeypatch.setattr(routes, "_workspace_scope", lambda **_: (None, "t1", "b1"))

    class Handlers:
        def get_sales_sources(self, **kw):
            return {"ok": True, **kw}

    router = APIRouter()
    routes.register_business_workspace_provider_routes(router=router, auth_bundle=None, provider_admin_handlers=Handlers())
    app = FastAPI()
    app.include_router(router)
    if flag:
        monkeypatch.setenv("BAI_SALES_CENTER_SOURCES_ENABLED", flag)
    else:
        monkeypatch.delenv("BAI_SALES_CENTER_SOURCES_ENABLED", raising=False)
    res = TestClient(app).get("/business-workspace/sales-sources?source=hubspot")
    assert res.status_code == code
    if code == 200:
        assert res.json()["requested"] == "hubspot"


def test_app_falls_back_to_the_hubspot_view_when_off():
    app = (Path(__file__).resolve().parents[3] / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
    assert "business-workspace/sales-sources" in app and "setSalesSources(null); // feature off" in app


def test_sales_sources_are_isolated_across_businesses_in_one_tenant(flow):
    from types import SimpleNamespace

    import entrypoints.api.provider_admin_route_handlers as mod

    for index, (user, business) in enumerate((("a", "b1"), ("b", "b2"), ("legacy", ""))):
        env = SimpleNamespace(decision=SimpleNamespace(decision_id=f"decision-{index}",
                                                       correlation_id=f"message-{index}"))
        handle_sales_pipeline({"tenant_id": "t1", "user_id": user, "business_id": business,
                               "op": "inbound", "arg": "Здравствуйте", "reply": "ok"},
                              flow.effects, env, event_store=flow.store, now_ms=1_800_000_000_000)

    class H(mod.ProviderAdminRouteHandlers):
        def list_provider_catalog(self, *, tenant_id, business_id):
            return {"providers": [{"provider_key": "telegram_bot", "connected": True}]}

    service = H(customer_event_store=flow.store)
    left = service.get_sales_sources(tenant_id="t1", business_id="b1")["sources"][0]
    right = service.get_sales_sources(tenant_id="t1", business_id="b2")["sources"][0]
    assert left["contacts"] == right["contacts"] == 1
    assert left["deals"] == right["deals"] == 1
    assert all(row["payload"].get("business_id") in ("b1", "b2", None) for row in flow.store.events)


def test_legacy_sales_facts_without_business_are_not_visible_in_web_projection(flow):
    from application.business_flows.projection import flow_rows
    run = partial(flow.run, partial(handle_sales_pipeline, now_ms=1_800_000_000_000))
    run(op="inbound", arg="legacy", reply="ok", user_id="legacy")
    assert flow_rows(flow.store, tenant_id="t1", event_type="sales_pipeline@v1")
    assert flow_rows(flow.store, tenant_id="t1", business_id="b1", event_type="sales_pipeline@v1") == []

"""P1-22: web communications center over the existing message and provider owners."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from application.business_flows import cockpit_sales as cc

RECEIPT = {"mode": "live", "operation": "message_send", "accepted": True, "status": "live_executed",
           "parsed_response": {"resource_id": "4242"}, "recorded_at_utc": "2026-11-18T10:00:00Z", "queue_job_id": "j1"}


def _msg(mid, direction, at):
    return SimpleNamespace(message_id=mid, channel="vk", direction=SimpleNamespace(value=direction),
                           customer_id="c1", conversation_id="v1", created_at_ms=at)


def test_states_come_only_from_provider_truth_and_queue():
    history = [{**RECEIPT, "parsed_response": {"resource_id": "4242", "delivery_state": "delivered"}},
               RECEIPT,
               {**RECEIPT, "parsed_response": {}, "recorded_at_utc": "2026-11-18T10:01:00Z"},  # no receipt
               {**RECEIPT, "accepted": False, "status": "rejected_provider_write_guard", "parsed_response": {},
                "error": {"category": "approval_required"}},
               {**RECEIPT, "operation": "message_read"},
               {**RECEIPT, "mode": "dry_run"}]
    jobs = [{"job_id": "q1", "state": "pending", "attempts": 0, "payload": {"operation": "message_send"}},
            {"job_id": "q2", "state": "pending", "attempts": 2, "payload": {"operation": "message_send"}},
            {"job_id": "q3", "state": "succeeded", "attempts": 1, "payload": {"operation": "message_send"}},
            {"job_id": "q4", "state": "pending", "attempts": 0, "payload": {"operation": "health_probe"}}]
    view = cc.communications_view(messages=[_msg("m1", "inbound", 2), _msg("m2", "outbound", 3), _msg("m3", "inbound", 5)],
                    providers={"vk_messaging": (history, jobs)})
    assert [r["message_id"] for r in view["inbound"]] == ["m3", "m1"]
    assert [r["receipt"] for r in view["outbound"]] == ["4242"]
    assert view["counts"] == {"inbound": 2, "outbound": 1, "unconfirmed": 2, "failed": 1, "queued": 1, "retries": 1}
    assert [r["state"] for r in view["unconfirmed"]] == ["unconfirmed", "unconfirmed"]
    assert view["failed"][0]["reason"] == "approval_required"
    assert view["retries"][0]["job_id"] == "q2" and view["pending_approval_source"] == "/control-plane/approvals/open"


def test_handler_reads_only_connected_messaging_providers(flow):
    import entrypoints.api.provider_admin_route_handlers as mod

    calls = []

    class Service:
        def list_provider_sync_history(self, *, provider_key, **_):
            calls.append(("history", provider_key))
            return [RECEIPT]

        def list_provider_queue_jobs(self, *, provider_key, **_):
            calls.append(("queue", provider_key))
            return []

    class H(mod.ProviderAdminRouteHandlers):
        def _service(self, business_id):
            return Service()

        def list_provider_catalog(self, *, tenant_id, business_id):
            return {"providers": [{"provider_key": "vk_messaging", "connected": True},
                                  {"provider_key": "max_messaging", "connected": False},
                                  {"provider_key": "hubspot", "connected": True}]}

    out = H(customer_event_store=flow.store).get_communications(tenant_id="t1", business_id="b1")
    assert out["providers"] == ["vk_messaging"] and {k for _, k in calls} == {"vk_messaging"}
    assert out["counts"]["outbound"] == 0 and out["counts"]["unconfirmed"] == 1 and out["inbound"] == []


@pytest.mark.parametrize("flag,code", [(None, 404), ("1", 200)])
def test_route_is_default_off(monkeypatch, flag, code):
    from fastapi import APIRouter, FastAPI
    from fastapi.testclient import TestClient

    import adapters.api.fastapi.business_workspace_provider_routes as routes

    monkeypatch.setattr(routes, "_workspace_scope", lambda **_: (None, "t1", "b1"))

    class Handlers:
        def get_communications(self, **kw):
            return {"counts": {}, **kw}

    router = APIRouter()
    routes.register_business_workspace_provider_routes(router=router, auth_bundle=None, provider_admin_handlers=Handlers())
    app = FastAPI()
    app.include_router(router)
    if flag:
        monkeypatch.setenv("BAI_COMMUNICATIONS_CENTER_ENABLED", flag)
    else:
        monkeypatch.delenv("BAI_COMMUNICATIONS_CENTER_ENABLED", raising=False)
    res = TestClient(app).get("/business-workspace/communications")
    assert res.status_code == code
    if code == 200:
        assert res.json()["business_id"] == "b1"


def test_app_hides_the_section_when_off_and_sends_nothing():
    app = (Path(__file__).resolve().parents[3] / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
    assert "business-workspace/communications" in app and "setCommunications(null); // feature off" in app
    section = app[app.index('communications-panel'):app.index('business-sales-title')]
    assert "postJson" not in section and "Отсюда ничего не отправляется" in section

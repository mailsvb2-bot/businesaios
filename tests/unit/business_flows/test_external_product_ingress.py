from __future__ import annotations

from functools import partial
from types import SimpleNamespace

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from adapters.api.fastapi.external_product_webhook_routes import register_external_product_webhook_routes
from core.policies.telegram.routes.business_flow_routes import handle_business_flow_routes
from runtime.handler_impl.domains.business_flow_ops import handle_business_admin
from runtime.integration import external_product_ingress as xpi
from tests.unit.business_flows.test_external_products import NOW, SECRET, _event, _sig


def _setup(flow, monkeypatch) -> str:
    run = partial(flow.run, partial(handle_business_admin, now_ms=NOW))
    monkeypatch.setenv("XP_CRM_SECRET", SECRET)
    cid = run(op="xp_add", arg="crm env:XP_CRM_SECRET CRM")[1].split()[2]
    run(op="xp_activate", arg=cid)
    return cid


def _wire(flow, monkeypatch):
    """Fake gateway: policy route -> handler, exactly what DecisionCore + executor do on the real path."""
    seen = []

    def gateway(*, issuer, executor, state):
        ctx = SimpleNamespace(state=state, callback_data="", callback_query_id="", args="", cmd="", is_admin=False)
        prop = handle_business_flow_routes(ctx, user_id=state.user_id)
        seen.append(prop)
        handle_business_admin({"tenant_id": state.tenant_id, **prop.payload}, flow.effects, SimpleNamespace(
            decision=SimpleNamespace(decision_id="d", correlation_id="c")), event_store=flow.store, now_ms=NOW)

    monkeypatch.setattr(xpi, "execute_runtime_decision", gateway)
    return seen


def test_forged_rejected_before_decision_and_authentic_reaches_owner(flow, monkeypatch) -> None:
    cid = _setup(flow, monkeypatch)
    seen = _wire(flow, monkeypatch)
    ts, body = NOW // 1000, _event()
    kw = {"core": None, "executor": None, "event_store": flow.store, "tenant_id": "t1", "owner_user_id": "owner1",
          "connector_id": cid, "raw_body": body, "now_ms": NOW}  # fmt: skip
    sent_before = len(flow.effects.sent)
    bad = {"X-Businesaios-Timestamp": str(ts), "X-Businesaios-Signature": "sha256=" + "0" * 64}
    assert xpi.ingest(headers=bad, **kw) == (403, "external_product_signature_invalid")
    assert xpi.ingest(headers=bad, **{**kw, "connector_id": "nope"})[0] == 403
    assert not seen and len(flow.effects.sent) == sent_before  # no decision, no owner spam
    good = {"X-Businesaios-Timestamp": str(ts), "X-Businesaios-Signature": _sig(body, ts)}
    assert xpi.ingest(headers=good, **kw) == (202, "accepted")
    assert seen[0].action == "business_admin@v1" and seen[0].payload["op"] == "xp_ingest"
    last = flow.effects.sent[-1]
    assert last["user_id"] == "owner1" and last["text"].startswith("accepted:")
    xpi.ingest(headers=good, **kw)
    assert flow.effects.sent[-1]["text"].startswith("duplicate:")
    assert xpi.ingest(headers=good, **{**kw, "owner_user_id": ""})[0] == 503


def test_http_route_maps_status() -> None:
    calls = []

    def ingest(**kw):
        calls.append(kw)
        return (403, "x") if kw["connector_id"] == "bad" else (202, "accepted")

    router = APIRouter()
    register_external_product_webhook_routes(router=router, ingest=ingest)
    app = FastAPI()
    app.include_router(router)
    c = TestClient(app)
    assert c.post("/businesaios/webhooks/xp/bad", content=b"{}").status_code == 403
    r = c.post("/businesaios/webhooks/xp/xp_1", content=b'{"a":1}', headers={"X-Businesaios-Signature": "s"})
    assert r.status_code == 202 and r.json() == {"status": "accepted"}
    assert calls[-1]["raw_body"] == b'{"a":1}' and calls[-1]["headers"]["x-businesaios-signature"] == "s"

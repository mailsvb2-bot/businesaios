"""Archive UIII XP end-to-end regressions using existing canonical business handlers."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from functools import partial
from types import SimpleNamespace

import pytest

from application.business_flows import cockpit as cp
from application.business_flows import external_products as xp
from runtime.execution.context import execution_business_scope
from runtime.handler_impl.domains.business_flow_ops import handle_business_admin, handle_business_ops_summary

NOW = 1_800_000_000_000
SECRET = "s" * 40


def observation(revision=1, state="active", previous=None):
    return {
        "observation_key": "signal-1", "kind": "attendance", "label": "Участие подтверждено",
        "observed_at": "2027-01-01T10:00:00Z", "provenance_ref": "proof:source-1",
        "revision": revision, "state": state, "supersedes_external_event_id": previous,
        "fresh_until": None, "quality": "source_verified", "limitations": ["Только эта встреча"],
    }


def event(eid="e1", **obs):
    if "previous" in obs:
        obs["supersedes_external_event_id"] = obs.pop("previous")
    return xp.parse_event(json.dumps({
        "version": 1, "type": "evidence", "event_id": eid,
        "occurred_at": "2027-01-01T10:00:00Z", "customer_ref": "person-1",
        "observation": {**observation(), **obs},
    }).encode())


def state(business="b1"):
    fact = xp.provision(xp.State(), product_key="uiii", display_name="UIII",
                        secret_ref="env:XP_SECRET", business_id=business)
    cid = fact["connector_id"]
    rows = [
        fact,
        {"step": "xp_activated", "connector_id": cid, "business_id": business},
        {"step": "xp_bound", "connector_id": cid, "business_id": business,
         "customer_ref": "person-1", "customer_id": "customer-1"},
    ]
    return rows, cid


def append(rows, cid, item, business="b1"):
    st = xp.replay(rows, business_id=business)
    fact, rid = xp.ingest_authenticated(
        st, st.connectors[cid], item,
        fingerprint=item["external_event_id"], received_at="2027-01-01T10:01:00+00:00",
    )
    if fact:
        rows.append(fact)
    return rid


def test_retraction_visible_and_original_still_idempotent():
    rows, cid = state()
    receipt = append(rows, cid, event())
    append(rows, cid, event("e2", revision=2, previous="e1"))
    append(rows, cid, event("e3", revision=3, state="retracted", previous="e2"))
    st = xp.replay(rows, business_id="b1")
    assert xp.latest_observations(st, customer_id="customer-1")[0]["observation"]["state"] == "retracted"
    assert xp.value_snapshot(st)["active_observations"] == 0
    assert xp.value_snapshot(st)["observations"] == 1
    assert append(rows, cid, event()) == receipt
    with pytest.raises(ValueError, match="advance"):
        append(rows, cid, event("late", revision=2, previous="e1"))


def test_live_cockpit_reopens_retracted_version_in_owner_scope():
    rows, cid = state()
    append(rows, cid, event())
    snap = cp.Snapshot(external_product_facts=rows, business_id="b1", now_ms=NOW)
    first, _ = cp.render(cp.parse("cpm:cust-time:customer-1"), snap, is_owner=True)
    assert "Участие подтверждено" in first
    append(rows, cid, event("e2", revision=2, state="retracted", previous="e1"))
    retracted, _ = cp.render(cp.parse("cpm:cust-time:customer-1"), snap, is_owner=True)
    assert "отозвано" in retracted and "ревизия 2" in retracted
    denied, _ = cp.render(cp.parse("cpm:cust-time:customer-1"), snap, is_owner=False)
    assert "Участие подтверждено" not in denied


def test_existing_business_handler_mutations_and_timeline(flow, monkeypatch):
    from interfaces.uiii.signals import xp_headers

    monkeypatch.setenv("XP_SECRET", SECRET)
    run = partial(flow.run, partial(handle_business_admin, now_ms=NOW))
    with execution_business_scope("business-1"):
        cid = run(op="xp_add", arg="uiii env:XP_SECRET UIII")[1].split()[2]
        run(op="xp_activate", arg=cid)
        run(op="xp_bind", arg=f"{cid} person-1 customer-1")
        body = json.dumps({
            "version": 1, "type": "evidence", "event_id": "ev-1",
            "occurred_at": "2027-01-01T10:00:00Z", "customer_ref": "person-1",
            "observation": observation(),
        }).encode()
        headers = xp_headers(body, secret=SECRET.encode(), now=datetime.fromtimestamp(NOW / 1000, UTC))
        run(op="xp_ingest", connector_id=cid, raw_body=body.decode(), headers=headers)
        assert flow.store.events[-1]["payload"]["business_id"] == "business-1"
        _, history = flow.run(partial(handle_business_ops_summary, now_ms=NOW),
                              op="cockpit", arg="cpm:cust-time:customer-1")
        assert "Участие подтверждено" in history
    with execution_business_scope("business-2"):
        assert cid not in run(op="xp_list")[1]


def test_signed_webhook_scope_is_not_taken_from_untrusted_body(flow, monkeypatch):
    from core.policies.telegram.routes.business_flow_routes import handle_business_flow_routes
    from interfaces.uiii.signals import xp_headers
    from runtime.integration import external_product_ingress as ingress

    monkeypatch.setenv("XP_SECRET", SECRET)
    rows, cid = state("business-1")
    for row in rows:
        flow.store.events.append({
            "tenant_id": "t1", "user_id": "owner", "event_type": "business_admin@v1",
            "timestamp_ms": 1, "payload": row,
        })
    body = json.dumps({
        "version": 1, "type": "evidence", "event_id": "ev-scope",
        "occurred_at": "2027-01-01T10:00:00Z", "customer_ref": "person-1",
        "observation": observation(),
    }).encode()
    headers = xp_headers(body, secret=SECRET.encode(), now=datetime.fromtimestamp(NOW / 1000, UTC))
    seen = []

    def gateway(*, issuer, executor, state):
        ctx = SimpleNamespace(
            state=state, callback_data="", callback_query_id="", args="", cmd="", is_admin=False,
        )
        action = handle_business_flow_routes(ctx, user_id=state.user_id)
        seen.append(action)
        with execution_business_scope(action.payload["business_id"]):
            handle_business_admin(
                {"tenant_id": "t1", **action.payload},
                flow.effects,
                SimpleNamespace(decision=SimpleNamespace(decision_id="d", correlation_id="c")),
                event_store=flow.store, now_ms=NOW,
            )

    monkeypatch.setattr(ingress, "execute_runtime_decision", gateway)
    assert ingress.ingest(core=None, executor=None, event_store=flow.store, tenant_id="t1",
                          owner_user_id="owner", connector_id=cid, raw_body=body,
                          headers=headers, now_ms=NOW) == (202, "accepted")
    assert seen[0].payload["business_id"] == "business-1"
    assert flow.store.events[-1]["payload"]["business_id"] == "business-1"


def test_feedback_suppresses_latest_without_restoring_old_version():
    rows, cid = state()
    append(rows, cid, event())
    newest = append(rows, cid, event("e2", revision=2, previous="e1"))
    rows.append({"step": "xp_feedback", "business_id": "b1", "receipt_id": newest,
                 "feedback": "wrong_customer"})
    st = xp.replay(rows, business_id="b1")
    assert xp.timeline_rows(st, customer_id="customer-1") == []
    assert len(xp.latest_observations(st, customer_id="customer-1")) == 1


def test_unbound_customer_reference_never_joins_another_reference():
    rows, cid = state()
    rows = [row for row in rows if row["step"] != "xp_bound"]
    a, other = event("a"), event("b")
    a["customer_ref"], other["customer_ref"] = "unknown-a", "unknown-b"
    append(rows, cid, a)
    append(rows, cid, other)
    st = xp.replay(rows, business_id="b1")
    assert len(xp.latest_observations(st)) == 2
    assert xp.timeline_rows(st, customer_id="customer-1") == []

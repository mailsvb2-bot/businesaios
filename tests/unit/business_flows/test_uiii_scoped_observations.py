"""Regression tests: XP scope, revision, tombstone and malformed source signals."""
from __future__ import annotations

import json

import pytest

from application.business_flows import external_products as xp


def observation(revision=1, state="active", previous=None):
    return {
        "observation_key": "meeting-1",
        "kind": "attendance",
        "label": "Подтверждено",
        "observed_at": "2027-01-01T10:00:00Z",
        "provenance_ref": "proof:meeting",
        "revision": revision,
        "state": state,
        "supersedes_external_event_id": previous,
        "quality": "source_verified",
        "limitations": [],
    }


def parsed(event_id, **changes):
    return xp.parse_event(json.dumps({
        "version": 1, "event_id": event_id, "type": "evidence",
        "occurred_at": "2027-01-01T10:00:00Z",
        "customer_ref": "ref-1",
        "observation": {**observation(), **changes},
    }).encode())


def test_business_scope_and_legacy_isolation():
    a = xp.provision(xp.State(), product_key="lms", display_name="LMS",
                     secret_ref="env:XP_SECRET", business_id="business-a")
    b = xp.provision(xp.State(), product_key="lms", display_name="LMS",
                     secret_ref="env:XP_SECRET", business_id="business-b")
    assert a["connector_id"] != b["connector_id"]
    assert not xp.replay([a, b]).connectors
    assert set(xp.replay([a, b], business_id="business-a").connectors) == {a["connector_id"]}
    assert set(xp.replay([a, b], business_id="business-b").connectors) == {b["connector_id"]}
    assert len(xp.replay([a, b], discover=True).connectors) == 2


def test_revision_supersession_and_tombstone_do_not_restore_old_value():
    record = xp.provision(xp.State(), product_key="lms", display_name="LMS",
                          secret_ref="env:XP_SECRET", business_id="business-a")
    connector_id = record["connector_id"]
    facts = [
        record,
        {"step": "xp_activated", "connector_id": connector_id, "business_id": "business-a"},
        {"step": "xp_bound", "connector_id": connector_id, "business_id": "business-a",
         "customer_ref": "ref-1", "customer_id": "customer-1"},
    ]

    def ingest(event):
        state = xp.replay(facts, business_id="business-a")
        change, receipt = xp.ingest_authenticated(
            state, state.connectors[connector_id], event,
            fingerprint=event["external_event_id"],
            received_at="2027-01-01T10:01:00+00:00",
        )
        if change:
            facts.append(change)
        return receipt

    first = ingest(parsed("ev-1"))
    ingest(parsed("ev-2", revision=2, previous="ev-1"))
    latest_receipt = ingest(parsed("ev-3", revision=3, state="retracted", previous="ev-2"))
    state = xp.replay(facts, business_id="business-a")
    assert state.receipts[first]["observation"]["state"] == "active"
    assert xp.latest_observations(state, customer_id="customer-1")[0]["receipt_id"] == latest_receipt
    assert xp.value_snapshot(state)["active_observations"] == 0
    assert "retracted" == xp.latest_observations(state)[0]["observation"]["state"]
    with pytest.raises(ValueError, match="advance"):
        ingest(parsed("ev-4", revision=2, previous="ev-1"))
    with pytest.raises(ValueError, match="supersession"):
        ingest(parsed("ev-5", revision=4, previous="invalid"))
    facts.append({"step": "xp_feedback", "business_id": "business-a",
                  "receipt_id": latest_receipt, "feedback": "wrong_customer"})
    assert xp.timeline_rows(xp.replay(facts, business_id="business-a"),
                            customer_id="customer-1") == []


@pytest.mark.parametrize("bad", [
    {"revision": 0}, {"revision": True}, {"label": ""},
    {"quality": ""}, {"provenance_ref": ""},
    {"fresh_until": "2026-12-01T00:00:00Z"},
    {"limitations": ["x"] * 9},
])
def test_bad_observation_fails_closed(bad):
    with pytest.raises(ValueError):
        parsed("bad", **bad)


def test_boolean_event_version_never_accepted():
    raw = {"version": True, "event_id": "e", "type": "evidence",
           "occurred_at": "2027-01-01T10:00:00Z"}
    with pytest.raises(ValueError, match="version"):
        xp.parse_event(json.dumps(raw).encode())


def test_cockpit_reads_only_matching_business_and_owner():
    from application.business_flows import cockpit as cp

    connector = xp.provision(
        xp.State(), product_key="lms", display_name="LMS",
        secret_ref="env:XP_SECRET", business_id="business-a",
    )
    cid = connector["connector_id"]
    rows = [
        connector,
        {"step": "xp_activated", "connector_id": cid, "business_id": "business-a"},
        {"step": "xp_bound", "connector_id": cid, "business_id": "business-a",
         "customer_ref": "ref-1", "customer_id": "customer-1"},
    ]
    st = xp.replay(rows, business_id="business-a")
    obs = parsed("e1")
    change, _ = xp.ingest_authenticated(
        st, st.connectors[cid], obs,
        fingerprint="fingerprint-1", received_at="2027-01-01T10:01:00+00:00",
    )
    rows.append(change)
    owner = cp.Snapshot(external_product_facts=rows, business_id="business-a",
                        now_ms=1_800_000_000_000)
    shown, _ = cp.render(cp.parse("cpm:cust-time:customer-1"), owner, is_owner=True)
    assert "Подтверждено" in shown and "LMS" in shown
    other = cp.Snapshot(external_product_facts=rows, business_id="business-b",
                        now_ms=1_800_000_000_000)
    hidden, _ = cp.render(cp.parse("cpm:cust-time:customer-1"), other, is_owner=True)
    assert "Подтверждено" not in hidden
    denied, _ = cp.render(cp.parse("cpm:cust-time:customer-1"), owner, is_owner=False)
    assert "Подтверждено" not in denied

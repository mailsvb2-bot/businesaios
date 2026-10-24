from datetime import UTC, datetime

import pytest

from application.business_flows import customer_timeline_sources as ts


def test_sales_event_entries():
    e = ts.sales_event_entry({"event_type": "stage_changed", "payload_json": '{"to_stage":"won"}',
                              "occurred_at": "2026-10-01T10:00:00Z"})
    assert e.title == "Продажа завершена" and e.kind == "sales:stage_changed"
    assert ts.sales_event_entry({"event_type": "internal", "occurred_at": "x"}) is None
    with pytest.raises(ts.TimelineInvariantViolation):
        ts.sales_event_entry({"event_type": "note_added", "occurred_at": "2026-10-01T10:00:00"})


def test_outcome_money_signs_and_reversal_lookup():
    paid = {"outcome_type": "order_paid", "amount_minor": 1500, "currency": "rub", "occurred_at": "2026-10-01T10:00:00Z"}
    assert ts.direct_signed_money(paid) == (1500, "rub")
    assert ts.direct_signed_money({"outcome_type": "refund_recorded", "amount_minor": 300, "currency": "RUB"}) == (-300, "RUB")
    with pytest.raises(ts.TimelineInvariantViolation):
        ts.direct_signed_money({**paid, "amount_minor": -1})
    rev = {"outcome_type": "outcome_reversal", "source_type": "outcome_event", "source_id": "o1",
           "occurred_at": "2026-10-02T10:00:00Z"}
    assert ts.outcome_money(rev, {"o1": paid}.get) == (-1500, "rub")
    assert ts.outcome_entry(rev, {"o1": paid}.get).detail == "-15.00 RUB"
    assert ts.outcome_money(rev, {}.get) is None


def test_external_observation_freshness_and_rejects():
    md = {"external_observation_schema": "2026-09-20.v2", "external_observation_kind": "visit",
          "external_observation_label": "Визит", "external_observation_provenance_ref": "r1",
          "external_observation_quality": "derived", "external_observation_observed_at": "2026-10-01T09:00:00Z"}
    now = datetime(2026, 10, 5, tzinfo=UTC)
    row = {"metadata_json": md, "connector_name": "YClients", "observation_fresh_until": "2026-10-03T00:00:00Z",
           "observation_revision": 2}
    e = ts.external_observation_entry(row, now=now)
    assert "возможно устарело" in e.detail and "ревизия 2" in e.detail
    assert ts.external_observation_entry({**row, "observation_state": "retracted"}, now=now).title.startswith("Внешнее")
    assert ts.external_observation_entry({**row, "connector_name": ""}, now=now) is None
    assert ts.external_observation_entry({"metadata_json": "{}"}, now=now) is None


def test_role_gates():
    assert ts.can_view_outcomes("manager") and not ts.can_view_outcomes("staff")
    assert ts.can_view_attribution("owner") and not ts.can_view_attribution("")

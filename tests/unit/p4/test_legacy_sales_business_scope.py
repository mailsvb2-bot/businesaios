from application.business_flows.projection import (
    flow_payloads,
    legacy_attribution,
    legacy_quarantine,
)
from tests.unit.business_flows.conftest import FlowStore


def _event(store, payload, n):
    store.events.append({"tenant_id": "t1", "user_id": "u1",
                         "event_type": "sales_pipeline@v1", "timestamp_ms": n,
                         "payload": payload})


def test_pre_d2_facts_never_leak_across_businesses(monkeypatch):
    monkeypatch.setenv("BAI_SALES_LEGACY_QUARANTINE_ENABLED", "1")
    store = FlowStore()
    _event(store, {"step": "lead_added", "lead_id": "lead_old", "name": "Secret"}, 1)
    assert flow_payloads(store, tenant_id="t1", business_id="b1", event_type="sales_pipeline@v1") == []
    assert legacy_quarantine(flow_payloads(store, tenant_id="t1", event_type="sales_pipeline@v1")) == [
        {"lead_id": "lead_old", "facts": 1}]
    _event(store, {"step": "legacy_leads_attributed", "lead_id": "lead_old", "business_id": "b1"}, 2)
    assert len(flow_payloads(store, tenant_id="t1", business_id="b1", event_type="sales_pipeline@v1")) == 2
    assert flow_payloads(store, tenant_id="t1", business_id="b2", event_type="sales_pipeline@v1") == []


def test_conflicting_claims_fail_closed(monkeypatch):
    monkeypatch.setenv("BAI_SALES_LEGACY_QUARANTINE_ENABLED", "1")
    store = FlowStore()
    for i, row in enumerate([
        {"step": "lead_added", "lead_id": "old"},
        {"step": "legacy_leads_attributed", "lead_id": "old", "business_id": "b1"},
        {"step": "legacy_leads_attributed", "lead_id": "old", "business_id": "b2"}], start=1):
        _event(store, row, i)
    assert legacy_attribution(flow_payloads(store, tenant_id="t1", event_type="sales_pipeline@v1")) == {}
    for business in ("b1", "b2"):
        assert all(row.get("step") != "lead_added" for row in flow_payloads(
            store, tenant_id="t1", business_id=business, event_type="sales_pipeline@v1"))

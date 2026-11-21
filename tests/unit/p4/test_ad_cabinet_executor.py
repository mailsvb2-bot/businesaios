from types import SimpleNamespace

from application.business_flows import ad_spend_guard as sg
from application.business_flows import event_series
from application.business_flows.projection import flow_payloads
from runtime.handler_impl.domains.business_flow_ops import handle_event_series
from tests.unit.business_flows.conftest import FlowEffects, FlowStore


class Effects(FlowEffects):
    def __init__(self, store, *, fail=False):
        super().__init__(store)
        self.fail = fail
        self.calls = []

    def ad_provider_action(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            return {"ok": False, "status": "unconfigured", "error": "AD_PROVIDER_TRANSPORT_NOT_CONFIGURED"}
        return {"ok": True, "status": "success",
                "result": {"campaigns": [{"campaign_id": "123", "name": "Тест",
                                          "state": "ON", "status": "ACCEPTED"}]}}


def _run(monkeypatch, *, business="b1", fail=False):
    monkeypatch.setenv("BAI_AD_CABINET_REFRESH_ENABLED", "1")
    store = FlowStore()
    effects = Effects(store, fail=fail)
    env = SimpleNamespace(decision=SimpleNamespace(decision_id="decision", correlation_id="correlation"))
    result = handle_event_series(
        {"tenant_id": "t1", "business_id": business, "user_id": "u1",
         "op": "spend_sync", "arg": ""},
        effects, env, event_store=store, now_ms=1_800_000_000_000)
    facts = event_series.expand(flow_payloads(store, tenant_id="t1", event_type="event_series@v1"))
    return result, effects, sg.cabinet_view(facts, business_id=business)


def test_cabinet_refresh_through_same_executor_and_event_owner(monkeypatch):
    _, effects, view = _run(monkeypatch)
    assert len(effects.calls) == 1
    assert effects.calls[0]["action"] == "list_campaigns"
    assert view["status"] == "synced" and view["campaigns"][0]["campaign_id"] == "123"


def test_unconfigured_provider_never_claims_success(monkeypatch):
    _, effects, view = _run(monkeypatch, fail=True)
    assert len(effects.calls) == 1
    assert view["status"] == "access_error"
    assert view["campaigns"] == []

from types import SimpleNamespace

import pytest

from application.business_autonomy import provider_truth_matrix as matrix
from core.events.event_types import KNOWN_EVENT_TYPES, PROVIDER_LIVE_EVIDENCE

NOW = 1800000000000

class Store:
    def __init__(self,events):
        self.events=events
    def iter_events(self,*,tenant_id,start_ms=0,end_ms=None,event_type=None):
        return (x for x in self.events if x["tenant_id"]==tenant_id and
                x["event_type"]==event_type and start_ms<=x["timestamp_ms"]<=end_ms)

def event(check, **changes):
    p=matrix.live_evidence_payload(business_id="b1",provider_key="vk_messaging",
        check=check,provider_ref="verified-"+check,decision_id="d",recorded_at_ms=NOW-1000)
    return {"tenant_id":"t1","source":"runtime.executor",
            "decision_id":"d","timestamp_ms":NOW-1000,
            "event_type":PROVIDER_LIVE_EVIDENCE,
            "payload":{**p,**changes}}

@pytest.fixture(autouse=True)
def provider(monkeypatch):
    monkeypatch.setattr(matrix,"MESSAGING_GUARDED_WRITE_PROVIDER_KEYS",frozenset({"vk_messaging"}))
    monkeypatch.setattr(matrix,"provider_truth_map",lambda:{"vk_messaging":
        SimpleNamespace(has_real_endpoint=True,has_placeholder_endpoint=False)})

def test_known_event_and_global_guard_remain_fail_closed():
    assert PROVIDER_LIVE_EVIDENCE in KNOWN_EVENT_TYPES
    assert matrix._GUARDED_WRITE_LIVE_READY == frozenset()

def test_all_five_fresh_executor_proofs_required():
    rows=[event(x) for x in matrix.LIVE_EVIDENCE_CHECKS]
    got=matrix.provider_channel_live_readiness(event_store=Store(rows),tenant_id="t1",
                                                business_id="b1",now_ms=NOW)["vk_messaging"]
    assert got["live_ready"] and not got["missing"]
    got_other=matrix.provider_channel_live_readiness(event_store=Store(rows),tenant_id="t1",
                                                business_id="b2",now_ms=NOW)["vk_messaging"]
    assert not got_other["live_ready"]

@pytest.mark.parametrize("bad",[
    {"mode":"dry_run"},{"ok":False},{"ok":"true"},{"provider_ref":""},
    {"recorded_at_ms":"1000"},{"decision_id":"different"},
])
def test_invalid_evidence_cannot_promote(bad):
    rows=[event(x) for x in matrix.LIVE_EVIDENCE_CHECKS[1:]]+[event("credentials",**bad)]
    assert not matrix.provider_channel_live_readiness(event_store=Store(rows),
        tenant_id="t1",business_id="b1",now_ms=NOW)["vk_messaging"]["live_ready"]

def test_untrusted_source_and_old_evidence_cannot_promote():
    rows=[event(x) for x in matrix.LIVE_EVIDENCE_CHECKS]
    rows[0]["source"]="external"
    assert not matrix.provider_channel_live_readiness(event_store=Store(rows),
        tenant_id="t1",business_id="b1",now_ms=NOW)["vk_messaging"]["live_ready"]
    rows[0]=event("credentials",recorded_at_ms=NOW-40*86400000)
    rows[0]["timestamp_ms"]=NOW-40*86400000
    assert not matrix.provider_channel_live_readiness(event_store=Store(rows),
        tenant_id="t1",business_id="b1",now_ms=NOW)["vk_messaging"]["live_ready"]

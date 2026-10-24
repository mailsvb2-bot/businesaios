from __future__ import annotations

import asyncio
import base64
from datetime import UTC, datetime

import pytest

from application.business_flows import external_products as xp
from application.business_flows import ucr_attendance_pilot as pilot

UID = base64.b64encode(b"user-1").decode()
REQ = {"conferenceId": "c1", "externalUserId": UID}
T0 = 1_800_000_000_000
NOW = datetime(2027, 1, 1, tzinfo=UTC)


def _att(**kw):
    base = {"externalUserId": UID, "firstJoinAtUnixMs": T0, "lastLeaveAtUnixMs": T0 + 3_900_000,
            "totalConnectedSeconds": 3900, "joinCount": 1, "mediaReadyCount": 1}  # fmt: skip
    return {"attendance": {**base, **kw}}


class _Gw:
    def __init__(self, result):
        self.result, self.calls = result, 0

    async def invoke_universal_conference(self, *, method, request):
        self.calls += 1
        return {"result": self.result}


def _state(status="xp_activated", bound="cust-1"):
    facts = [{"step": "xp_provisioned", "connector_id": "c1", "product_key": "ucr", "display_name": "UCR",
              "secret_ref": "vault:xp.c1"}, {"step": status, "connector_id": "c1"},
             {"step": "xp_bound", "connector_id": "c1", "customer_ref": "ref-1", "customer_id": bound}]  # fmt: skip
    return xp.replay(facts)


def _sync(st, result, **kw):
    return asyncio.run(pilot.sync_ucr_attendance_pilot(
        st, connector_id="c1", customer_id=kw.get("customer", "cust-1"), customer_ref="ref-1", canonical_request=REQ,
        observation_key="k", gateway=_Gw(result), received=NOW))  # fmt: skip


def test_helpers_match_donor():
    with pytest.raises(ValueError):
        pilot.received_at(datetime(2027, 1, 1))
    assert pilot.received_at(NOW) == NOW
    eid = pilot.event_id(observation_key="k", provenance_ref="p", revision=2)
    assert eid.startswith("ucr-attendance:") and eid.endswith(":r2") and len(eid.split(":")[1]) == 40
    with pytest.raises(ValueError):
        pilot.payload_fingerprint(connector_id="c", customer_ref="r", event={"observation": None})


def test_sync_emits_evidence_then_revisions_and_dedupes():
    st = _state()
    out = _sync(st, _att())
    fact = out["fact"]
    assert out["persisted"] and fact["step"] == "xp_event" and fact["event_type"] == "evidence"
    assert fact["customer_id"] == "cust-1" and fact["observation"]["revision"] == 1
    assert fact["metadata"] == {"source_adapter": "ucr_attendance_pilot"} and "vault" not in repr(fact)
    st2 = xp.replay([*[{"step": "xp_provisioned", "connector_id": "c1", "product_key": "ucr", "display_name": "UCR",
                        "secret_ref": "vault:xp.c1"}, {"step": "xp_activated", "connector_id": "c1"},
                       {"step": "xp_bound", "connector_id": "c1", "customer_ref": "ref-1", "customer_id": "cust-1"}],
                     fact])  # fmt: skip
    same = _sync(st2, _att())
    assert same["fact"] is None and same["receipt_id"] == fact["receipt_id"] and not same["persisted"]
    longer = _sync(st2, _att(totalConnectedSeconds=4000, lastLeaveAtUnixMs=T0 + 4_000_000))
    assert longer["fact"]["observation"]["revision"] == 2
    assert longer["fact"]["observation"]["supersedes_external_event_id"] == fact["external_event_id"]


def test_no_attendance_no_fact():
    out = _sync(_state(), {"attendance": {"externalUserId": UID}})
    assert out["fact"] is None and not out["persisted"]


@pytest.mark.parametrize(("st", "customer"), [(_state("xp_disabled"), "cust-1"), (_state(), "other")])
def test_requires_active_connector_and_matching_binding(st, customer):
    with pytest.raises(ValueError):
        _sync(st, _att(), customer=customer)

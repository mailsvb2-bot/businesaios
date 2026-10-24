from __future__ import annotations

import asyncio
import base64

import pytest

from application.business_flows.bookings import Slot
from interfaces.ucr import attendance as ua

UID = base64.b64encode(b"user-1").decode()
REQ = {"conferenceId": "c1", "externalUserId": UID}
T0 = 1_800_000_000_000


def _att(**kw):
    base = {
        "externalUserId": UID,
        "firstJoinAtUnixMs": T0,
        "lastLeaveAtUnixMs": T0 + 3_900_000,
        "totalConnectedSeconds": 3900,
        "joinCount": 1,
        "mediaReadyCount": 1,
    }
    return {"attendance": {**base, **kw}}


class _Gateway:
    def __init__(self, result):
        self.result, self.calls = result, []

    async def invoke_universal_conference(self, *, method, request):
        self.calls.append((method, dict(request)))
        return {"result": self.result}


def _read(result, head=None):
    gw = _Gateway(result)
    out = asyncio.run(
        ua.read_ucr_attendance_observation(gateway=gw, canonical_request=REQ, observation_key="k", current_head=head)
    )
    assert gw.calls[0][0] is ua.UcrUniversalConferenceMethod.GET_PARTICIPANT_ATTENDANCE
    return out


def test_verified_attendance_becomes_observation_and_attendance_fact() -> None:
    read = _read(_att())
    obs = read.observation
    assert obs.label == "Участие в онлайн-событии подтверждено: 65 мин" and obs.revision == 1
    assert obs.quality == "source_verified" and obs.provenance_ref.startswith("ucr-attendance:")
    slot = Slot("s1", "Встреча", T0 - 1, 60, status="booked", customer_id="cust")
    fact = ua.attendance_fact(read, slot, now_ms=T0 + 4_000_000)
    assert fact["step"] == "attendance" and fact["status"] == "attended" and fact["evidence"] == obs.provenance_ref


def test_revision_chain_and_no_show_and_connected() -> None:
    head = ua.ObservationHead("k", 2, "ev-2")
    obs = _read(_att(), head).observation
    assert obs.revision == 3 and obs.supersedes_external_event_id == "ev-2"
    with pytest.raises(ValueError, match="another key"):
        _read(_att(), ua.ObservationHead("other", 1, "e"))
    zero = _read({"attendance": {"externalUserId": UID}})
    slot = Slot("s1", "Встреча", T0 - 1, 60, status="booked", customer_id="cust")
    assert zero.observation is None and ua.attendance_fact(zero, slot, now_ms=T0)["status"] == "no_show"
    live = _read(_att(connected=True, currentConnectedSeconds=10, lastLeaveAtUnixMs=None))
    assert ua.attendance_fact(live, slot, now_ms=T0) is None
    assert any("подключён" in x for x in live.observation.limitations)


@pytest.mark.parametrize(
    "result",
    [
        _att(externalUserId=base64.b64encode(b"someone").decode()),
        _att(extra=1),
        _att(joinCount=0),
        _att(lastLeaveAtUnixMs=T0 - 1),
        _att(joinCount=True),
        _att(firstJoinAtUnixMs=None),
        {"attendance": "x"},
    ],
)
def test_invalid_source_evidence_is_rejected(result) -> None:
    with pytest.raises(ValueError):
        _read(result)

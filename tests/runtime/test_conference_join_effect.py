from __future__ import annotations

import base64
import json

import pytest

from application.business_flows import public_events as pe
from runtime._internal.effects_domains import conference as mod


class Log:
    def __init__(self):
        self.events = []
    def emit(self, **kw):
        self.events.append(kw)


class FakeGateway:
    def __init__(self, lifecycle="scheduled"):
        self.calls, self.lifecycle = [], lifecycle
    async def invoke_universal_conference(self, *, method, request, idempotency_key):
        self.calls.append((method.value, dict(request), idempotency_key))
        if method.value == "CreateConference":
            return {"result": {"conference": {"conferenceId": {"value": base64.b64encode(b"c-1").decode()},
                                              "lifecycle": "UNIVERSAL_CONFERENCE_LIFECYCLE_" + self.lifecycle.upper()}}}
        if method.value == "IssueJoinGrant":
            return {"result": {"grant": {"joinUrl": "https://ucr.example/j/secret", "expiresAtUnixMs": "60"}}}
        return {"result": {}}


class Fx(mod.ConferenceEffectsMixin):
    def __init__(self, gw):
        self.event_log, self.ucr_gateway = Log(), gw


def _plan():
    steps = [{"method": "CreateConference", "idempotency_key": "k1", "tenant_id": "t", "request": {"external_conference_id": "x", "mode": "webinar"}},
             {"method": "EnsureParticipant", "idempotency_key": "k2", "tenant_id": "t", "request": {"role": "attendee", "external_user_id": "u"}},
             {"method": "IssueJoinGrant", "idempotency_key": "k3", "tenant_id": "t", "request": {"external_user_id": "u", "ttl_seconds": 60}, "store_url": False}]
    return steps


@pytest.fixture(autouse=True)
def _exec(monkeypatch):
    monkeypatch.setattr(mod, "assert_called_from_executor", lambda: None)


def test_runs_plan_and_never_logs_url():
    gw = FakeGateway()
    fx = Fx(gw)
    out = fx.run_conference_join_plan(decision_id="d", correlation_id="c", tenant_id="t", user_id="u", plan=_plan(), integration_id="i")
    assert out["join_url"].startswith("https://") and out["conference_ref"] == "c-1"
    assert [c[0] for c in gw.calls] == ["CreateConference", "EnsureParticipant", "IssueJoinGrant"]
    def b(v):
        return base64.b64encode(v.encode()).decode()
    assert gw.calls[0][1] == {"scope": {"tenantId": {"value": b("t")}}, "integrationId": {"value": b("i")}, "idempotencyKey": "k1",
                              "externalConferenceId": b("x"), "mode": "UNIVERSAL_CONFERENCE_MODE_WEBINAR"}
    assert gw.calls[1][1]["conferenceId"] == {"value": b("c-1")} and gw.calls[1][1]["role"] == "CONFERENCE_PARTICIPANT_ROLE_ATTENDEE"
    assert gw.calls[2][1]["ttlSeconds"] == 60 and gw.calls[2][1]["usePolicy"] == "JOIN_GRANT_USE_POLICY_SINGLE_USE"
    assert "secret" not in json.dumps(fx.event_log.events) and fx.event_log.events[0]["payload"]["url_stored"] is False


def test_rejects_bad_plans_and_ended():
    fx = Fx(FakeGateway())
    bad = _plan()
    bad[-1]["store_url"] = True
    for p in ([], bad, [dict(_plan()[0], tenant_id="x")] + _plan()[1:], [dict(_plan()[0], method="DeleteAll")] + _plan()[1:]):
        with pytest.raises(ValueError):
            fx.run_conference_join_plan(decision_id="d", correlation_id="c", tenant_id="t", user_id="u", plan=p, integration_id="i")
    with pytest.raises(RuntimeError):
        Fx(FakeGateway("ended")).run_conference_join_plan(decision_id="d", correlation_id="c", tenant_id="t", user_id="u", plan=_plan(), integration_id="i")


def test_disabled_gateway_makes_no_call(monkeypatch):
    monkeypatch.delenv("BUSINESAIOS_UCR_GATEWAY_ENABLED", raising=False)
    fx = Fx(None)
    assert fx.run_conference_join_plan(decision_id="d", correlation_id="c", tenant_id="t", user_id="u", plan=_plan(), integration_id="i") == {"ok": False, "reason": "ucr_disabled"}
    assert fx.event_log.events == []


def test_real_public_events_plans_run_end_to_end():
    from datetime import UTC, datetime
    ev = pe.PubEvent("e1", "T", "webinar", datetime(2026, 1, 1, tzinfo=UTC).isoformat(), "Europe/Moscow", "s",
                     status="published", provider_key="ucr")
    b = pe.Board(events={"e1": ev}, registrations={"r1": pe.Registration("r1", "e1", "h", "t", "A")})
    for plan in (pe.attendee_join_plan(b, ev, "r1", position=0, owner_member_id="m1", tenant_id="t"),
                 pe.owner_join_plan(ev, position=0, owner_member_id="m1", actor_member_id="m1", can_manage=True, tenant_id="t")):
        assert mod.validate_join_plan(plan, tenant_id="t") == plan
        gw = FakeGateway()
        fx = Fx(gw)
        assert fx.run_conference_join_plan(decision_id="d", correlation_id="c", tenant_id="t", user_id="u", plan=plan, integration_id="i")["ok"]
        assert len(gw.calls) == len(plan) and "secret" not in json.dumps(fx.event_log.events)


def test_proto_fields_match_pinned_ucr_proto():
    # field names from proto/ucr/v1/universal_conference.proto @4e8668b3 (proto3 JSON camelCase)
    want = {"CreateConference": {"scope", "integrationId", "externalConferenceId", "idempotencyKey", "mode"},
            "EnsureParticipant": {"scope", "conferenceId", "integrationId", "externalUserId", "role", "idempotencyKey"},
            "PrepareConferenceRuntime": {"scope", "conferenceId", "integrationId", "idempotencyKey"},
            "TransitionConference": {"scope", "conferenceId", "target", "idempotencyKey", "integrationId"},
            "SetEntryOpen": {"scope", "conferenceId", "entryOpen", "idempotencyKey", "integrationId"},
            "IssueJoinGrant": {"scope", "conferenceId", "integrationId", "externalUserId", "ttlSeconds", "usePolicy", "idempotencyKey"}}
    req = {"external_conference_id": "x", "mode": "webinar", "external_user_id": "u", "role": "host",
           "lifecycle": "waiting", "open": True, "ttl_seconds": 900}
    for m, fields in want.items():
        assert set(mod.proto_request(m, req, tenant_id="t", integration_id="i", idempotency_key="k", conference_id="c")) == fields
    with pytest.raises(ValueError):
        mod.proto_request("EnsureParticipant", {"role": "boss", "external_user_id": "u"}, tenant_id="t", integration_id="i", idempotency_key="k", conference_id="c")

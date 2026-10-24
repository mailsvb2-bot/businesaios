"""Managed (UCR) conference join execution — the only place join plans touch the network.

Plans come from application.business_flows.public_events (attendee_join_plan/owner_join_plan).
The executor runs each idempotent UniversalConference RPC through interfaces.ucr.gateway with the
sealed transport. The join grant URL is returned to the caller once and NEVER written to the
event log (events carry only methods, keys and the conference ref). Disabled gateway -> no call.
"""

from __future__ import annotations

import asyncio
from typing import Any

from runtime.security.runtime_asserts import assert_called_from_executor

PLAN_METHODS = frozenset({"CreateConference", "EnsureParticipant", "PrepareConferenceRuntime",
                          "TransitionConference", "SetEntryOpen", "IssueJoinGrant"})
_URL_KEYS = ("join_url", "joinUrl", "url", "grant_url", "token")


def validate_join_plan(plan: object, *, tenant_id: str) -> list[dict[str, Any]]:
    if not isinstance(plan, list) or not plan or len(plan) > 12:
        raise ValueError("conference_plan_invalid")
    steps = []
    for s in plan:
        if not isinstance(s, dict) or s.get("method") not in PLAN_METHODS or s.get("tenant_id") != tenant_id:
            raise ValueError("conference_plan_step_invalid")
        if not isinstance(s.get("idempotency_key"), str) or not isinstance(s.get("request"), dict):
            raise ValueError("conference_plan_step_invalid")
        steps.append(s)
    if steps[0]["method"] != "CreateConference" or steps[-1]["method"] != "IssueJoinGrant" or steps[-1].get("store_url") is not False:
        raise ValueError("conference_plan_shape_invalid")
    return steps


# proto3-JSON shaping verified against mailsvb2-bot/Universal-Communication-Runtime
# proto/ucr/v1/universal_conference.proto @4e8668b3 (TenantScope scope, OpaqueId{value: base64},
# bytes as base64, enum names, camelCase); responses are {"result": <oneof conference|grant|error>}.
_MODES = {"meeting": 1, "webinar": 2, "broadcast": 3, "audio_room": 4}
_ROLES = {"owner": "OWNER", "host": "HOST", "moderator": "MODERATOR", "speaker": "SPEAKER", "attendee": "ATTENDEE"}
_LIFECYCLES = ("SCHEDULED", "WAITING", "LIVE", "ENDING", "ENDED")


def _b64(v: str) -> str:
    import base64
    raw = str(v).encode()
    if not raw or len(raw) > 128:
        raise ValueError("ucr_opaque_id_invalid")
    return base64.b64encode(raw).decode("ascii")


def _oid(v: str) -> dict[str, str]:
    return {"value": _b64(v)}


def proto_request(method: str, req: dict[str, Any], *, tenant_id: str, integration_id: str, idempotency_key: str,
                  conference_id: str) -> dict[str, Any]:
    out: dict[str, Any] = {"scope": {"tenantId": _oid(tenant_id)}, "integrationId": _oid(integration_id),
                           "idempotencyKey": idempotency_key}
    if method == "CreateConference":
        mode = str(req.get("mode") or "meeting").lower()
        if mode not in _MODES:
            raise ValueError("ucr_conference_mode_invalid")
        out |= {"externalConferenceId": _b64(req["external_conference_id"]),
                "mode": "UNIVERSAL_CONFERENCE_MODE_" + mode.upper()}
        return out
    if not conference_id:
        raise ValueError("ucr_conference_id_missing")
    out["conferenceId"] = _oid(conference_id)
    if method == "EnsureParticipant":
        role = _ROLES.get(str(req.get("role")))
        if role is None:
            raise ValueError("ucr_participant_role_invalid")
        out |= {"externalUserId": _b64(req["external_user_id"]), "role": "CONFERENCE_PARTICIPANT_ROLE_" + role}
    elif method == "TransitionConference":
        target = str(req.get("lifecycle") or "").upper()
        if target not in _LIFECYCLES:
            raise ValueError("ucr_lifecycle_invalid")
        out["target"] = "UNIVERSAL_CONFERENCE_LIFECYCLE_" + target
    elif method == "SetEntryOpen":
        out["entryOpen"] = bool(req.get("open"))
    elif method == "IssueJoinGrant":
        ttl = int(req.get("ttl_seconds") or 0)
        if not 1 <= ttl <= 86_400:
            raise ValueError("ucr_join_ttl_invalid")
        out |= {"externalUserId": _b64(req["external_user_id"]), "ttlSeconds": ttl,
                "usePolicy": "JOIN_GRANT_USE_POLICY_SINGLE_USE"}
    return out


def _result(resp: Any, key: str) -> dict[str, Any]:
    res = resp.get("result") if isinstance(resp, dict) else None
    if not isinstance(res, dict):
        raise RuntimeError("ucr_result_missing")
    if res.get("error") is not None:
        raise RuntimeError("ucr_error")
    body = res.get(key) if key else res
    return body if isinstance(body, dict) else {}


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _scrub(v) for k, v in value.items() if k not in _URL_KEYS}
    return value


class ConferenceEffectsMixin:
    event_log: Any
    ucr_gateway: Any = None  # injectable (tests); default built from env with the sealed transport

    def _ucr_client(self) -> Any:
        if self.ucr_gateway is not None:
            return self.ucr_gateway
        from interfaces.ucr.gateway import UcrGatewayClient, ucr_gateway_config
        from runtime._internal.effects_clients.ucr_gateway_transport import SyncRequestUcrGatewayTransport
        cfg = ucr_gateway_config()
        if not cfg.enabled:
            return None
        return UcrGatewayClient(config=cfg, transport=SyncRequestUcrGatewayTransport())

    def run_conference_join_plan(self, *, decision_id: str, correlation_id: str, tenant_id: str, user_id: str,
                                 plan: list[dict[str, Any]], integration_id: str) -> dict[str, Any]:
        assert_called_from_executor()
        from interfaces.ucr.gateway import UcrUniversalConferenceMethod
        steps = validate_join_plan(plan, tenant_id=tenant_id)
        client = self._ucr_client()
        if client is None:
            return {"ok": False, "reason": "ucr_disabled"}

        async def run() -> tuple[str, dict[str, Any]]:
            import base64
            conference_id, grant = "", {}
            for s in steps:
                m = s["method"]
                req = proto_request(m, s["request"], tenant_id=tenant_id, integration_id=integration_id,
                                    idempotency_key=s["idempotency_key"], conference_id=conference_id)
                resp = await client.invoke_universal_conference(
                    method=UcrUniversalConferenceMethod(m), request=req, idempotency_key=s["idempotency_key"])
                if m == "CreateConference":
                    conf = _result(resp, "conference")
                    raw = (conf.get("conferenceId") or {}).get("value") if isinstance(conf.get("conferenceId"), dict) else None
                    if not raw:
                        raise RuntimeError("ucr_conference_ref_missing")
                    conference_id = base64.b64decode(str(raw), validate=True).decode()
                    if str(conf.get("lifecycle") or "").endswith(("_ENDING", "_ENDED")):
                        raise RuntimeError("managed conference is no longer joinable")
                elif m == "IssueJoinGrant":
                    grant = _result(resp, "grant")
                else:
                    _result(resp, "")
            return conference_id, grant

        conference_ref, result = asyncio.run(run())
        join_url = str(result.get("joinUrl") or "")
        if not join_url.startswith("https://"):
            raise RuntimeError("ucr_join_grant_invalid")
        self.event_log.emit(
            event_type="conference_join_issued", source="ucr", user_id=str(user_id), decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload={"tenant_id": tenant_id, "conference_ref": conference_ref,
                     "steps": [{"method": s["method"], "idempotency_key": s["idempotency_key"]} for s in steps],
                     "grant": _scrub({k: v for k, v in result.items() if k != "joinUrl"}), "url_stored": False})
        return {"ok": True, "conference_ref": conference_ref, "join_url": join_url}


__all__ = ["ConferenceEffectsMixin", "PLAN_METHODS", "proto_request", "validate_join_plan"]

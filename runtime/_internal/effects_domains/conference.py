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
_URL_KEYS = ("join_url", "url", "grant_url", "token")


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
            conference_ref, last = "", {}
            for s in steps:
                req = {**s["request"], "tenant_id": tenant_id, "integration_id": integration_id}
                if conference_ref:
                    req["conference_ref"] = conference_ref
                last = await client.invoke_universal_conference(
                    method=UcrUniversalConferenceMethod(s["method"]), request=req, idempotency_key=s["idempotency_key"])
                if s["method"] == "CreateConference":
                    res = last.get("result") if isinstance(last, dict) else None
                    conference_ref = str((res or {}).get("conference_ref") or (res or {}).get("conference_id") or "")
                    if not conference_ref:
                        raise RuntimeError("ucr_conference_ref_missing")
                    if str((res or {}).get("lifecycle") or "").lower() in {"ending", "ended"}:
                        raise RuntimeError("managed conference is no longer joinable")
            return conference_ref, last

        conference_ref, grant = asyncio.run(run())
        result = grant.get("result") if isinstance(grant, dict) else None
        join_url = str((result or {}).get("join_url") or "")
        if not join_url.startswith("https://"):
            raise RuntimeError("ucr_join_grant_invalid")
        self.event_log.emit(
            event_type="conference_join_issued", source="ucr", user_id=str(user_id), decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload={"tenant_id": tenant_id, "conference_ref": conference_ref,
                     "steps": [{"method": s["method"], "idempotency_key": s["idempotency_key"]} for s in steps],
                     "grant": _scrub(result or {}), "url_stored": False})
        return {"ok": True, "conference_ref": conference_ref, "join_url": join_url}


__all__ = ["ConferenceEffectsMixin", "PLAN_METHODS", "validate_join_plan"]

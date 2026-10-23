"""VK Callback API / MAX webhook ingress for native routes, mapped through the existing
``runtime.messaging_ingress`` adapters. Verification only; decisions stay with DecisionCore."""

from __future__ import annotations

import hmac
from typing import Any

from application.business_flows import native_channels as nc
from application.business_flows import promotions as pm
from runtime.messaging_ingress import max_payload_to_messaging_event, vk_payload_to_messaging_event


def handle_inbound(*, routes: dict[str, nc.Route], platform: str, rid: str, payload: dict[str, Any],
                   secret_header: str = "", server_key: str, tenant_id: str) -> tuple[str, Any]:  # fmt: skip
    """Returns ``("confirm", code)`` | ``("event", MessagingIngressEvent)`` | ``("ignored", reason)`` | ``("rejected", reason)``."""
    r = routes.get(rid)
    if r is None or r.platform != platform or r.status != "active":
        return "rejected", "route_inactive"
    expected = nc.webhook_secret(server_key, rid)
    if platform == "vk":
        if str(payload.get("group_id") or "") != r.external_id:
            return "rejected", "group_mismatch"
        if payload.get("type") == "confirmation":
            return ("confirm", r.confirmation_code) if r.confirmation_code else ("rejected", "no_confirmation_code")
        if not hmac.compare_digest(str(payload.get("secret") or ""), expected):
            return "rejected", "secret_invalid"
        if payload.get("type") != "message_new":
            return "ignored", str(payload.get("type") or "")
        return "event", vk_payload_to_messaging_event(payload, tenant_id=tenant_id)
    if not hmac.compare_digest(str(secret_header or ""), expected):
        return "rejected", "secret_invalid"
    return "event", max_payload_to_messaging_event(payload, tenant_id=tenant_id)


def promotion_touch(*, camps: dict[str, pm.Campaign], text: str, platform: str, subject: str,
                    identities: dict[tuple[str, str], str]) -> dict[str, Any] | None:  # fmt: skip
    """``/start cpa_<token>`` (or bare payload) from a known VK/MAX identity -> verified opened fact."""
    word = str(text or "").replace("/start", "").strip()
    token = pm.parse_start_payload(word)
    if token is None:
        return None
    return pm.open_channel_for_identity(
        camps, token, platform=platform, external_subject=subject, identities=identities
    )[1]

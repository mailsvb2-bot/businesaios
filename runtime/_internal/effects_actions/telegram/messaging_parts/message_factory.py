from __future__ import annotations

from runtime.tenancy import normalize_tenant_id
from runtime.messaging.outbound_message import OutboundMessage


def resolve_tenant_id(*, tenant_id: str | None, track_payload: dict | None) -> str:
    for candidate in (
        tenant_id,
        (track_payload or {}).get("tenant_id") if isinstance(track_payload, dict) else None,
    ):
        resolved = normalize_tenant_id(candidate)
        if resolved:
            return resolved
    return "unknown_tenant"


def build_outbound_message(*, decision_id: str, correlation_id: str, user_id: str, text: str, tenant_id: str, reply_markup: dict | None, callback_query_id: str | None, track_event_type: str | None, track_payload: dict | None, channel: str, priority, critical: bool) -> OutboundMessage:
    return OutboundMessage(
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        tenant_id=resolve_tenant_id(tenant_id=tenant_id, track_payload=track_payload),
        user_id=str(user_id),
        channel=str(channel or "telegram"),
        text=str(text or ""),
        reply_markup=reply_markup,
        callback_query_id=callback_query_id,
        track_event_type=track_event_type,
        track_payload=track_payload,
        priority=str(priority or "normal"),
        critical=bool(critical),
        payload={
            "text": str(text or ""),
            "reply_markup": reply_markup,
            "track_event_type": track_event_type,
            "track_payload": dict(track_payload or {}),
            "callback_query_id": callback_query_id,
            "execution_entrypoint": "runtime.execution.decision_execution_service",
        },
    )

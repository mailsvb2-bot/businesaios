from __future__ import annotations

import uuid

from contracts.messaging_event_identity import stable_transport_message_id

from .contracts import MessageEnvelope


def default_correlation_id_factory() -> str:
    return f"corr-{uuid.uuid4().hex}"


def parse_inbound_payload(*, channel: str, raw: dict, correlation_id_factory=default_correlation_id_factory) -> MessageEnvelope:
    payload = dict(raw or {})
    provider_message_id = str(payload.get("message_id", "") or "").strip()
    original_payload = payload.get("raw")
    identity_payload = original_payload if isinstance(original_payload, dict) else payload
    message_id = provider_message_id or stable_transport_message_id(
        channel=channel,
        payload=identity_payload,
    )
    envelope = MessageEnvelope(
        channel=channel,
        user_id=str(payload.get("user_id", "")).strip(),
        text=str(payload.get("text", "")).strip(),
        message_id=message_id,
        correlation_id=str(payload.get("correlation_id", "")).strip() or correlation_id_factory(),
        metadata=payload,
    )
    envelope.validate()
    return envelope

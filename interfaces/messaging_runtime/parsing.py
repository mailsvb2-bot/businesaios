from __future__ import annotations

import uuid

from .contracts import MessageEnvelope


def default_correlation_id_factory() -> str:
    return f"corr-{uuid.uuid4().hex}"


def parse_inbound_payload(*, channel: str, raw: dict, correlation_id_factory=default_correlation_id_factory) -> MessageEnvelope:
    envelope = MessageEnvelope(
        channel=channel,
        user_id=str(raw.get("user_id", "")).strip(),
        text=str(raw.get("text", "")).strip(),
        message_id=str(raw.get("message_id", "")).strip(),
        correlation_id=str(raw.get("correlation_id", "")).strip() or correlation_id_factory(),
        metadata=dict(raw),
    )
    envelope.validate()
    return envelope

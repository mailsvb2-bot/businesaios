from __future__ import annotations

from runtime.messaging.outbound_message import OutboundMessage


def delivery_preview(msg: OutboundMessage, *, limit: int = 120) -> str:
    return str(msg.text or "")[: int(limit)]


def sender_identity(msg: OutboundMessage, *, fallback: str = "") -> str:
    return str(msg.metadata.get("sender") or fallback or "")


def normalize_inbound_dict(payload: dict | None) -> dict:
    return dict(payload or {})

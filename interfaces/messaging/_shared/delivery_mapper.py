from __future__ import annotations

from runtime.messaging.delivery_result import DeliveryResult
from runtime.messaging.outbound_message import OutboundMessage


def map_delivery_result(*, msg: OutboundMessage, raw: dict) -> DeliveryResult:
    payload = dict(raw or {})
    delivered = bool(payload.get("delivered", payload.get("ok", False))) and not bool(payload.get("noop", False))
    return DeliveryResult(
        ok=delivered,
        channel=msg.channel,
        mode=str(payload.get("mode") or "unknown"),
        external_id=str(payload.get("external_id") or ""),
        detail={
            "provider": payload.get("provider"),
            "reason": payload.get("reason"),
            "endpoint": payload.get("endpoint"),
            "sender": payload.get("sender"),
            "delivery_key": payload.get("delivery_key"),
            "text_preview": payload.get("text_preview"),
            "delivered": delivered,
            "noop": bool(payload.get("noop", False)),
            "execution_state": payload.get("execution_state"),
            "observability_hint": payload.get("observability_hint"),
        },
    )

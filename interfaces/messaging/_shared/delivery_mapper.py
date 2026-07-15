from __future__ import annotations

from runtime.messaging.delivery_result import DeliveryResult
from runtime.messaging.outbound_message import OutboundMessage


def map_delivery_result(*, msg: OutboundMessage, raw: dict) -> DeliveryResult:
    payload = dict(raw or {})
    noop = bool(payload.get("noop", False))
    external_id = str(payload.get("external_id") or "").strip()
    delivered = bool(payload.get("delivered", False)) and not noop and bool(external_id)
    accepted = bool(payload.get("accepted", False)) and not noop and bool(external_id)
    return DeliveryResult(
        ok=bool(delivered or accepted),
        channel=msg.channel,
        mode=str(payload.get("mode") or "unknown"),
        external_id=external_id,
        detail={
            "provider": payload.get("provider"),
            "reason": payload.get("reason"),
            "endpoint": payload.get("endpoint"),
            "sender": payload.get("sender"),
            "delivery_key": payload.get("delivery_key"),
            "text_preview": payload.get("text_preview"),
            "accepted": accepted,
            "delivered": delivered,
            "noop": noop,
            "execution_state": payload.get("execution_state"),
            "observability_hint": payload.get("observability_hint"),
        },
    )

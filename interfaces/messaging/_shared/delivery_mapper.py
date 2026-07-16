from __future__ import annotations

from runtime.messaging.delivery_result import DeliveryResult
from runtime.messaging.outbound_message import OutboundMessage


def map_delivery_result(*, msg: OutboundMessage, raw: dict) -> DeliveryResult:
    payload = dict(raw or {})
    provider_ok = payload.get("ok") is True
    noop = bool(payload.get("noop", False))
    external_id = str(payload.get("external_id") or "").strip()
    external_receipt = bool(external_id) and external_id != msg.delivery_key
    delivered = (
        provider_ok
        and bool(payload.get("delivered", False))
        and not noop
        and external_receipt
    )
    accepted = (
        provider_ok
        and bool(payload.get("accepted", False))
        and not noop
        and external_receipt
    )
    reason = payload.get("reason")
    if external_id == msg.delivery_key:
        reason = "provider_receipt_not_external"
    elif not provider_ok and (payload.get("accepted") or payload.get("delivered")):
        reason = reason or "provider_result_contradictory"
    return DeliveryResult(
        ok=bool(delivered or accepted),
        channel=msg.channel,
        mode=str(payload.get("mode") or "unknown"),
        external_id=external_id if delivered or accepted else "",
        detail={
            "provider": payload.get("provider"),
            "reason": reason,
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

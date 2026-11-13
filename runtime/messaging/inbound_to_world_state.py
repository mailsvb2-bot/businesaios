from __future__ import annotations

from dataclasses import dataclass, field

from runtime.messaging.inbound_message import InboundMessage

_CALLBACK_MARKERS = ("cpm:", "cp:", "menu:", "menu_", "settings:", "ads:", "admin:", "state:", "gift:", "sub:", "pay:", "autopilot:", "ceo:", "growth:", "profit_sprint:")


@dataclass(frozen=True)
class WorldStateMessageInput:
    tenant_id: str
    user_id: str
    channel: str
    message_text: str
    correlation_id: str
    transport_message_id: str
    session: dict[str, object] = field(default_factory=dict)
    product: dict[str, object] = field(default_factory=dict)


def map_inbound_to_world_state(msg: InboundMessage) -> WorldStateMessageInput:
    md, text = dict(msg.metadata or {}), str(msg.text)
    stripped = text.strip()
    command, args = "", stripped
    if stripped.startswith("/"):
        head, _, tail = stripped.partition(" ")
        command, args = head.split("@", 1)[0].lower(), tail.strip()
    callback = str(md.get("callback_data") or "")
    is_cb = bool(callback or md.get("callback_query_id") or (
        not command and any(stripped.startswith(marker) for marker in _CALLBACK_MARKERS)))
    if is_cb and not callback:
        callback = stripped
    session = {"source": "messaging", "channel": msg.canonical_identity.channel,
               "transport_message_id": msg.canonical_identity.transport_message_id,
               "chat_id": str(md.get("chat_id") or ""), "text": text,
               "command": command, "args": args, "is_callback": is_cb,
               "callback_data": callback, "callback_query_id": md.get("callback_query_id")}
    # Provider metadata is not a tenant/business membership proof. The canonical
    # authenticated binding must supply business authority, never a webhook field.
    return WorldStateMessageInput(
        tenant_id=str(msg.tenant_id), user_id=str(msg.user_id), channel=str(msg.channel),
        message_text=text, correlation_id=str(msg.correlation_id or ""),
        transport_message_id=str(msg.transport_message_id or ""), session=session,
        product={"business_id": msg.verified_business_id} if msg.verified_business_id else {},
    )

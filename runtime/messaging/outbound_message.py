from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


def _stable_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def transport_guard_blocks(guard, message=None) -> bool:
    if not callable(guard):
        return False
    try:
        return bool(str((guard() if message is None else guard(message)) or "").strip())
    except Exception:
        return True


@dataclass(frozen=True)
class OutboundMessage:
    decision_id: str
    correlation_id: str
    tenant_id: str
    user_id: str
    channel: str
    text: str
    business_id: str = ""
    attachments: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    reply_markup: dict | None = None
    callback_query_id: str | None = None
    track_event_type: str | None = None
    track_payload: dict | None = None
    priority: str = "normal"
    critical: bool = True
    payload: dict | None = None
    transport_guard: Callable[[OutboundMessage], str] | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        normalized_attachments = tuple(dict(item) for item in self.attachments if isinstance(item, dict))
        object.__setattr__(self, "attachments", normalized_attachments)
        base_payload = dict(self.payload or {})
        if not base_payload:
            base_payload = {
                "text": str(self.text or ""),
                **({"attachments": [dict(item) for item in normalized_attachments]} if normalized_attachments else {}),
                "reply_markup": self.reply_markup,
                "track_event_type": self.track_event_type,
                "track_payload": dict(self.track_payload or {}),
                "callback_query_id": self.callback_query_id,
            }
        object.__setattr__(self, "payload", base_payload)
        object.__setattr__(self, "channel", str(self.channel or "telegram"))
        object.__setattr__(self, "priority", str(self.priority or "normal"))
        object.__setattr__(self, "text", str(self.text or ""))
        object.__setattr__(self, "business_id", str(self.business_id or "").strip())

    @property
    def payload_digest(self) -> str:
        return hashlib.sha256(_stable_json(dict(self.payload or {})).encode("utf-8")).hexdigest()

    @property
    def delivery_key(self) -> str:
        base = {
            "decision_id": str(self.decision_id or ""),
            "correlation_id": str(self.correlation_id or ""),
            "tenant_id": str(self.tenant_id or ""),
            "business_id": str(self.business_id or ""),
            "user_id": str(self.user_id or ""),
            "channel": str(self.channel or ""),
            "text": str(self.text or ""),
            "attachments": [dict(item) for item in self.attachments],
            "reply_markup": self.reply_markup,
            "callback_query_id": str(self.callback_query_id or ""),
            "payload_digest": self.payload_digest,
        }
        return hashlib.sha256(_stable_json(base).encode("utf-8")).hexdigest()

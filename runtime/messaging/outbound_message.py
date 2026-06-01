from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


def _stable_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


@dataclass(frozen=True)
class OutboundMessage:
    decision_id: str
    correlation_id: str
    tenant_id: str
    user_id: str
    channel: str
    text: str
    reply_markup: dict | None = None
    callback_query_id: str | None = None
    track_event_type: str | None = None
    track_payload: dict | None = None
    priority: str = "normal"
    critical: bool = True
    payload: dict | None = None

    def __post_init__(self) -> None:
        base_payload = dict(self.payload or {})
        if not base_payload:
            base_payload = {
                "text": str(self.text or ""),
                "reply_markup": self.reply_markup,
                "track_event_type": self.track_event_type,
                "track_payload": dict(self.track_payload or {}),
                "callback_query_id": self.callback_query_id,
            }
        object.__setattr__(self, "payload", base_payload)
        object.__setattr__(self, "channel", str(self.channel or "telegram"))
        object.__setattr__(self, "priority", str(self.priority or "normal"))
        object.__setattr__(self, "text", str(self.text or ""))

    @property
    def payload_digest(self) -> str:
        return hashlib.sha256(_stable_json(dict(self.payload or {})).encode("utf-8")).hexdigest()

    @property
    def delivery_key(self) -> str:
        base = {
            "decision_id": str(self.decision_id or ""),
            "correlation_id": str(self.correlation_id or ""),
            "tenant_id": str(self.tenant_id or ""),
            "user_id": str(self.user_id or ""),
            "channel": str(self.channel or ""),
            "text": str(self.text or ""),
            "reply_markup": self.reply_markup,
            "callback_query_id": str(self.callback_query_id or ""),
            "payload_digest": self.payload_digest,
        }
        return hashlib.sha256(_stable_json(base).encode("utf-8")).hexdigest()

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class CrmWebhookEvent:
    provider_key: str
    event_type: str
    event_id: str
    payload: Mapping[str, object] = field(default_factory=dict)


def crm_webhook_event_schema() -> dict[str, object]:
    return {"type": "object", "required": ["provider_key", "event_type", "event_id", "payload"], "properties": {"provider_key": {"type": "string", "minLength": 1}, "event_type": {"type": "string", "minLength": 1}, "event_id": {"type": "string", "minLength": 1}, "payload": {"type": "object"}}, "additionalProperties": False}


__all__ = ["CrmWebhookEvent", "crm_webhook_event_schema"]

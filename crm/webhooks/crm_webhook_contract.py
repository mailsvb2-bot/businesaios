from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class CrmWebhookEvent:
    provider_key: str
    event_type: str
    event_id: str
    payload: Mapping[str, object] = field(default_factory=dict)

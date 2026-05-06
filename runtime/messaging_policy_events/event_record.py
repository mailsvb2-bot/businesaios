from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from runtime.messaging_policy_trace.iso_time import epoch_ms_to_iso


@dataclass(frozen=True)
class MessagingPolicyEventRecord:
    tenant_id: str
    user_id: str
    decision_id: str
    correlation_id: str
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    source: str = 'messaging_policy'
    timestamp_ms: int = 0
    event_id: str = ''

    @property
    def created_at(self) -> str:
        return epoch_ms_to_iso(int(self.timestamp_ms or 0))

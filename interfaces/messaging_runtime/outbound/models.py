from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DeliveryAttemptState:
    dedupe_key: str
    correlation_id: str
    channel: str
    attempt_count: int = 0
    last_error: str | None = None
    status: str = "queued"


@dataclass(frozen=True)
class DeadLetterRecord:
    dedupe_key: str
    correlation_id: str
    channel: str
    reason: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

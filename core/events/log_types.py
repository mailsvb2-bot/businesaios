"""Event log types and Event schema."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class Event:
    event_id: str
    user_id: str
    source: str
    event_type: str
    timestamp_ms: int
    payload: Dict[str, Any]
    decision_id: Optional[str]
    correlation_id: Optional[str]


__all__ = ["Event"]

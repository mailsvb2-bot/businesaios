from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict


@dataclass(frozen=True)
class BudgetGuardTriggered:
    event_id: str
    snapshot_id: str
    guard_code: str
    severity: str
    message: str
    occurred_at: datetime
    details: Dict[str, Any] = field(default_factory=dict)

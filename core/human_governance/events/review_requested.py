from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping


@dataclass(frozen=True)
class ReviewRequested:
    review_id: str
    decision_id: str
    requested_at: datetime
    requested_by: str
    reason: str
    metadata: Mapping[str, Any]

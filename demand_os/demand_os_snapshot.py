from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class DemandOsSnapshot:
    request_count: int = 0
    decision_count: int = 0
    delivery_count: int = 0
    last_request_id: str = ""
    last_business_id: str = ""
    metrics: dict[str, float] = field(default_factory=dict)

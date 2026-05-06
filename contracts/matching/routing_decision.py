from __future__ import annotations
from dataclasses import dataclass, field

@dataclass(frozen=True, slots=True)
class RoutingDecision:
    request_id: str = ""
    selected_business_id: str | None = None
    runner_up_business_ids: tuple[str, ...] = ()
    trace: dict[str, object] = field(default_factory=dict)
    requires_manual_review: bool = False

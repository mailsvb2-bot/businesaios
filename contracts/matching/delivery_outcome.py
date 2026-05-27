from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class DeliveryOutcome:
    request_id: str = ""
    business_id: str = ""
    delivery_status: str = ""
    channel: str = ""
    detail: str = ""
    delivered_at_ms: int | None = None

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LeadDeliveryStatus:
    request_id: str
    business_id: str
    channel: str
    status: str
    detail: str = ""

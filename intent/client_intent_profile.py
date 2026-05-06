from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class ClientIntentProfile:
    service_type: str
    urgency: str
    budget_band: str
    quality_band: str
    location_mode: str
    confidence: float
    labels: tuple[str, ...]

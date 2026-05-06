from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class CrmStateSlice:
    tenant_id: str
    business_id: str
    provider_key: str
    funnel_health: str = 'unknown'
    open_deals: int = 0
    stale_deals: int = 0
    recent_conversions: int = 0
    metadata: Mapping[str, object] = field(default_factory=dict)

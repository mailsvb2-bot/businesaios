from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class CrmStateSnapshot:
    tenant_id: str
    business_id: str
    provider_key: str
    open_deals: int = 0
    won_deals_last_30d: int = 0
    lost_deals_last_30d: int = 0
    stalled_deals: int = 0
    metadata: Mapping[str, object] = field(default_factory=dict)

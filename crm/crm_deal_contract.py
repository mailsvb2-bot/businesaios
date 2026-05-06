from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Mapping


@dataclass(frozen=True)
class CrmDeal:
    deal_id: str
    title: str
    pipeline_key: str
    stage_key: str
    value: Decimal | None = None
    currency: str | None = None
    owner_id: str | None = None
    contact_id: str | None = None
    custom_fields: Mapping[str, object] = field(default_factory=dict)

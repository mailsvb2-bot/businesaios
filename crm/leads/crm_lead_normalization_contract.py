from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class RawLeadPayload:
    tenant_id: str
    business_id: str
    payload: Mapping[str, object] = field(default_factory=dict)

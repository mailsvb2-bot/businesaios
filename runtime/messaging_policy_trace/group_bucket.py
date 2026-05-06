from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TraceBucket:
    tenant_id: str
    user_id: str
    correlation_id: str
    records: list = field(default_factory=list)

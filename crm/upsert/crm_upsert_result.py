from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class CrmUpsertResult:
    entity_type: str
    operation: str
    record_id: str | None
    verified: bool
    reason: str
    metadata: Mapping[str, object] = field(default_factory=dict)

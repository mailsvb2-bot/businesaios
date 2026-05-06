from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class CrmUpsertRequest:
    entity_type: str
    dedup_key: str
    payload: Mapping[str, object]
    idempotency_key: str
    merge_strategy: str = 'merge_non_empty'
    metadata: Mapping[str, object] = field(default_factory=dict)

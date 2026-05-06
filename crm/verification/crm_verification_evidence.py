from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class CrmVerificationEvidence:
    provider_key: str
    entity_type: str
    record_id: str | None
    payload: Mapping[str, object] = field(default_factory=dict)

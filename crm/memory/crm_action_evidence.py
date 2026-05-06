from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class CrmActionEvidence:
    action_type: str
    provider_key: str
    record_id: str | None
    verified: bool
    payload: Mapping[str, object] = field(default_factory=dict)

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class CrmOutcomeEvidence:
    signal_type: str
    provider_key: str
    payload: Mapping[str, object] = field(default_factory=dict)

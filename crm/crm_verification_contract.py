from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class CrmVerificationRequest:
    entity_type: str
    provider_key: str
    record_id: str | None
    expected_fields: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class CrmVerificationResult:
    verified: bool
    provider_key: str
    entity_type: str
    record_id: str | None
    reason: str
    evidence: Mapping[str, object] = field(default_factory=dict)

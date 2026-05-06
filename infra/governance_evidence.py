from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GovernanceEvidence:
    evidence_id: str
    evidence_type: str
    payload: dict = field(default_factory=dict)

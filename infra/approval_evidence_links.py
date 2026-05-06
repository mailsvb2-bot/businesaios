from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ApprovalEvidenceLink:
    request_id: str
    required_steps: tuple[str, ...] = field(default_factory=tuple)
    approved_steps: tuple[str, ...] = field(default_factory=tuple)
    fully_approved: bool = False

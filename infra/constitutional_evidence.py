from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ConstitutionalEvidence:
    action_name: str
    actor_scope: str
    allowed: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)
    escalation_route: tuple[str, ...] = field(default_factory=tuple)

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PolicyConstitution:
    name: str
    immutable_rules: tuple[str, ...] = field(default_factory=tuple)
    mandatory_escalation_actions: tuple[str, ...] = field(default_factory=tuple)
    protected_actions: tuple[str, ...] = field(default_factory=tuple)

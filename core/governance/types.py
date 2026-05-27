from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PolicyHealth:
    policy_name: str
    healthy: bool


@dataclass(frozen=True)
class PolicyState:
    policy_name: str = "default"
    enabled: bool = True
    metadata: dict[str, object] = field(default_factory=dict)

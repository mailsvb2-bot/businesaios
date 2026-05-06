from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RollbackRecord:
    rollback_id: str
    actor: str
    target_name: str
    reason: str
    policy_version_id: str | None = None
    metadata: dict = field(default_factory=dict)

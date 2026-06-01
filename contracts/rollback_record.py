from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RollbackRecord:
    rollback_id: str = ''
    action_id: str = ''
    reason: str = ''

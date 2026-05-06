from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ChangeRequest:
    change_id: str
    actor: str
    change_type: str
    target_name: str
    payload: dict = field(default_factory=dict)

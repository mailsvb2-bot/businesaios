from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ApprovalRequest:
    request_id: str
    actor: str
    approval_type: str
    target_name: str
    required_steps: tuple[str, ...]
    payload: dict = field(default_factory=dict)

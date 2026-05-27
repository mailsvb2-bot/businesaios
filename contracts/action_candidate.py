from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ActionCandidate:
    candidate_id: str = ''
    action_type: str = ''
    channel: str = ''
    expected_value: float = 0.0

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class FeedbackSnapshot:
    feedback_id: str = ''
    kind: str = ''
    value: str = ''

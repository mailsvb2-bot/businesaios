from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class DecisionSpaceNarrowingAudit:
    removed_candidates: List[str] = field(default_factory=list)
    counts_by_reason: Dict[str, int] = field(default_factory=dict)

    def record(self, action_type: str, why: str) -> None:
        self.removed_candidates.append(f"{action_type}:{why}")
        self.counts_by_reason[why] = self.counts_by_reason.get(why, 0) + 1

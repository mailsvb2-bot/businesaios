from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DecisionSpaceNarrowingAudit:
    removed_candidates: list[str] = field(default_factory=list)
    counts_by_reason: dict[str, int] = field(default_factory=dict)

    def record(self, action_type: str, why: str) -> None:
        self.removed_candidates.append(f"{action_type}:{why}")
        self.counts_by_reason[why] = self.counts_by_reason.get(why, 0) + 1

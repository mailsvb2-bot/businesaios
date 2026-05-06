from __future__ import annotations
from dataclasses import dataclass, field
from typing import List
from kernel.decision_result import DecisionResult


@dataclass
class DecisionHistory:
    items: List[DecisionResult] = field(default_factory=list)

    def append(self, result: DecisionResult) -> None:
        self.items.append(result)

    def all(self) -> list[DecisionResult]:
        return list(self.items)

    def latest(self) -> DecisionResult | None:
        return self.items[-1] if self.items else None

    def approved(self) -> list[DecisionResult]:
        return [item for item in self.items if item.approved]

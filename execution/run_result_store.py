from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from contracts.action_result import ActionResult


@dataclass
class ActionResultStore:
    results: Dict[str, ActionResult] = field(default_factory=dict)

    def save(self, action_id: str, result: ActionResult) -> None:
        self.results[action_id] = result

    def get(self, action_id: str) -> ActionResult:
        return self.results[action_id]


__all__ = ['ActionResultStore']

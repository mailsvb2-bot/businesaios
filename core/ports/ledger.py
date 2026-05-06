from __future__ import annotations

from typing import Protocol


class DecisionLedgerPort(Protocol):
    def is_executed(self, decision_id: str) -> bool: ...
    def try_mark_executed(self, decision_id: str) -> bool: ...

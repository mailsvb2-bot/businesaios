from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class Transition:
    state: dict[str, Any]
    action: dict[str, Any]
    reward_minor: int
    meta: dict[str, Any]


class DatasetBuilder:
    def __init__(self, *, reward_computer: Any) -> None:
        self._reward = reward_computer

    def build_for_decisions(self, *, tenant_id: str, decision_ids: list[str], lookback_days: int) -> list[Transition]:
        out: list[Transition] = []
        for did in decision_ids:
            t = self._reward.transition_for_decision(
                tenant_id=str(tenant_id),
                decision_id=str(did),
                lookback_days=int(lookback_days),
            )
            if t is not None:
                out.append(t)
        return out

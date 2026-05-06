from __future__ import annotations

from dataclasses import dataclass
from typing import List

from core.ads.rl.dataset import Transition


@dataclass(frozen=True)
class OPEReport:
    ok: bool
    reason: str
    n: int
    avg_reward_minor: int


class OPEGate:
    def __init__(self, *, min_transitions: int = 30, min_avg_reward_minor: int = -10_000_00) -> None:
        self._min_n = int(min_transitions)
        self._min_avg = int(min_avg_reward_minor)

    def check(self, transitions: List[Transition]) -> OPEReport:
        n = len(transitions)
        if n < self._min_n:
            return OPEReport(ok=False, reason=f"too_few_transitions<{self._min_n}", n=n, avg_reward_minor=0)
        total = sum(int(t.reward_minor) for t in transitions)
        avg = int(total / n) if n else 0
        if avg < self._min_avg:
            return OPEReport(ok=False, reason=f"avg_reward_too_low<{self._min_avg}", n=n, avg_reward_minor=avg)
        return OPEReport(ok=True, reason="ok", n=n, avg_reward_minor=avg)

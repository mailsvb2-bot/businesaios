from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List

from core.ads.rl.dataset import Transition
from core.ads.rl.ope import OPEGate, OPEReport
from core.ads.rl.policy_store import PolicyStore


@dataclass(frozen=True)
class TrainReport:
    ok: bool
    reason: str
    n: int
    policy_version: int | None = None
    ope_reason: str | None = None
    avg_reward_minor: int | None = None


class RLTrainer:
    def __init__(self, *, store: PolicyStore, ope_gate: OPEGate | None = None) -> None:
        self._store = store
        self._ope = ope_gate or OPEGate()

    def train(self, *, tenant_id: str, transitions: list[Transition]) -> TrainReport:
        ope: OPEReport = self._ope.check(transitions)
        if not ope.ok:
            return TrainReport(ok=False, reason="ope_blocked", n=len(transitions), ope_reason=ope.reason, avg_reward_minor=ope.avg_reward_minor)

        total = sum(int(t.reward_minor) for t in transitions)
        avg = int(total / len(transitions)) if transitions else 0
        params = {}
        params["budget_multiplier_x1000"] = 1050 if avg > 0 else 950
        params["avg_reward_minor"] = int(avg)
        params["trained_ms"] = int(time.time() * 1000)
        params["dataset_n"] = int(len(transitions))

        snap = self._store.put(tenant_id=str(tenant_id), policy_id="ads.rl.policy.v1", params=params)
        return TrainReport(ok=True, reason="trained", n=len(transitions), policy_version=int(snap.version), avg_reward_minor=int(avg))

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from core.ads.rl.dataset import Transition
from core.ads.rl.ope import OPEGate, OPEReport
from core.ads.rl.policy_store import PolicyStore

_POLICY_NAMESPACE = uuid.UUID("88b1ed63-5a45-4c28-9bc0-826653ba4fd9")


@dataclass(frozen=True)
class TrainReport:
    ok: bool
    reason: str
    n: int
    policy_version: int | None = None
    ope_reason: str | None = None
    avg_reward_minor: int | None = None


def _policy_id(*, tenant_id: str, decision_id: str) -> str:
    if not str(decision_id).strip():
        return "ads.rl.policy.v1"
    return str(
        uuid.uuid5(
            _POLICY_NAMESPACE,
            f"businesaios:ads-rl-policy:{tenant_id}:{decision_id}",
        )
    )


class RLTrainer:
    def __init__(self, *, store: PolicyStore, ope_gate: OPEGate | None = None) -> None:
        self._store = store
        self._ope = ope_gate or OPEGate()

    def train(
        self,
        *,
        tenant_id: str,
        transitions: list[Transition],
        user_id: str = "system",
        decision_id: str = "",
        correlation_id: str = "",
    ) -> TrainReport:
        tenant = str(tenant_id)
        rows = list(transitions)
        policy_id = _policy_id(
            tenant_id=tenant,
            decision_id=str(decision_id),
        )
        latest = self._store.get_latest(tenant_id=tenant)
        if (
            latest is not None
            and str(decision_id).strip()
            and latest.policy_id == policy_id
        ):
            stored_n = int(latest.params.get("dataset_n") or len(rows))
            stored_avg = int(latest.params.get("avg_reward_minor") or 0)
            return TrainReport(
                ok=True,
                reason="idempotent_replay",
                n=stored_n,
                policy_version=int(latest.version),
                ope_reason="replayed",
                avg_reward_minor=stored_avg,
            )

        ope: OPEReport = self._ope.check(rows)
        if not ope.ok:
            return TrainReport(
                ok=False,
                reason="ope_blocked",
                n=len(rows),
                ope_reason=ope.reason,
                avg_reward_minor=ope.avg_reward_minor,
            )

        total = sum(int(transition.reward_minor) for transition in rows)
        avg = int(total / len(rows)) if rows else 0
        params = {
            "budget_multiplier_x1000": 1050 if avg > 0 else 950,
            "avg_reward_minor": int(avg),
            "trained_ms": int(time.time() * 1000),
            "dataset_n": int(len(rows)),
        }

        snapshot = self._store.put(
            tenant_id=tenant,
            policy_id=policy_id,
            params=params,
            user_id=str(user_id or "system"),
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            event_id=policy_id if str(decision_id).strip() else None,
        )
        return TrainReport(
            ok=True,
            reason="trained",
            n=len(rows),
            policy_version=int(snapshot.version),
            ope_reason=ope.reason,
            avg_reward_minor=int(avg),
        )

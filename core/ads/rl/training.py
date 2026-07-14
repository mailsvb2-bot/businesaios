from __future__ import annotations

import math
import time
import uuid
from dataclasses import dataclass
from typing import Iterable

from config.ads_rl_policy import DEFAULT_ADS_RL_TRAINING_POLICY, AdsRLTrainingPolicy

from .contracts import AdsPolicySnapshotV1, AdsTransitionV1
from .ope import OPEGate
from .store import PolicyStore

_RL_POLICY_NAMESPACE = uuid.UUID("88b1ed63-5a45-4c28-9bc0-826653ba4fd9")


@dataclass(frozen=True)
class TrainReportV1:
    ok: bool
    reason: str
    n: int
    policy_version: int | None = None
    ope_reason: str | None = None
    avg_reward_minor: float | None = None


class RLTrainer:
    """Small, deterministic trainer.

    Learns a stable budget multiplier from observed transitions and appends a
    policy snapshot only if OPE passes. One signed Decision maps to one policy
    identity so delivery retries cannot create another policy version.
    """

    def __init__(
        self,
        *,
        store: PolicyStore,
        ope_gate: OPEGate,
        policy: AdsRLTrainingPolicy | None = None,
    ) -> None:
        self._store = store
        self._ope = ope_gate
        self._policy = policy or DEFAULT_ADS_RL_TRAINING_POLICY

    def train(
        self,
        *,
        tenant_id: str,
        transitions: Iterable[AdsTransitionV1],
        user_id: str = "system",
        decision_id: str = "",
        correlation_id: str = "",
    ) -> TrainReportV1:
        tenant = str(tenant_id)
        rows = list(transitions)
        n = len(rows)
        if n == 0:
            return TrainReportV1(ok=False, reason="no_data", n=0)

        deterministic_policy_id = (
            str(
                uuid.uuid5(
                    _RL_POLICY_NAMESPACE,
                    f"ads-rl-policy:{tenant}:{decision_id}",
                )
            )
            if str(decision_id).strip()
            else str(uuid.uuid4())
        )
        latest = self._store.latest(tenant_id=tenant)
        if (
            latest is not None
            and str(decision_id).strip()
            and latest.policy_id == deterministic_policy_id
        ):
            avg_reward = sum(float(row.reward.reward_minor) for row in rows) / float(n)
            return TrainReportV1(
                ok=True,
                reason="idempotent_replay",
                n=n,
                policy_version=int(latest.version),
                ope_reason="replayed",
                avg_reward_minor=float(avg_reward),
            )

        ope = self._ope.evaluate(transitions=rows)
        if not ope.ok:
            return TrainReportV1(
                ok=False,
                reason="ope_failed",
                n=n,
                ope_reason=ope.reason,
                avg_reward_minor=ope.avg_reward_minor,
            )

        weighted_sum = 0.0
        weight_total = 0.0
        for row in rows:
            reward = float(row.reward.reward_minor)
            weight = min(
                self._policy.max_importance_weight,
                self._policy.importance_weight_numerator
                / max(self._policy.min_propensity, float(row.propensity)),
            )
            weighted_sum += reward * weight
            weight_total += weight

        estimate = weighted_sum / max(self._policy.min_weight_total, weight_total)
        scaled = math.tanh(estimate / self._policy.reward_scale_minor)
        multiplier_x1000 = int(
            round(
                self._policy.base_multiplier_x1000
                + self._policy.multiplier_span_x1000 * scaled
            )
        )
        multiplier_x1000 = max(
            self._policy.min_multiplier_x1000,
            min(self._policy.max_multiplier_x1000, multiplier_x1000),
        )

        latest_version = int(latest.version) if latest is not None else 0
        snapshot = AdsPolicySnapshotV1(
            policy_id=deterministic_policy_id,
            tenant_id=tenant,
            version=latest_version + 1,
            created_ms=int(time.time() * 1000),
            params={
                "budget_multiplier_x1000": multiplier_x1000,
                "min_daily_budget_minor": self._policy.min_daily_budget_minor,
                "max_daily_budget_minor": self._policy.max_daily_budget_minor,
                "notes": self._policy.policy_note,
            },
        )
        self._store.append(
            snapshot,
            user_id=str(user_id or "system"),
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
        )

        return TrainReportV1(
            ok=True,
            reason="trained",
            n=n,
            policy_version=snapshot.version,
            ope_reason=ope.reason,
            avg_reward_minor=ope.avg_reward_minor,
        )

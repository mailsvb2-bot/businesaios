"""Learning system (online + offline scaffolding).

This module MUST NOT perform side-effects (no policy activation/rollback directly).
It only:
- observes rewards
- maintains statistics
- proposes deploy/rollback candidates

Actual deployment/rollback is executed ONLY via RuntimeExecutor after a DecisionEnvelope
(action deploy_policy / rollback_policy) passes Guard + Ledger.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass

from config.final_hidden_logic_policy import DEFAULT_LEARNING_SYSTEM_POLICY
from core.tenancy.tenant import current_tenant_id
from kernel.world_state import WorldStateV1


@dataclass
class BanditStats:
    ltv_sum: float = DEFAULT_LEARNING_SYSTEM_POLICY.zero_value

    n: int = 0
    reward_sum: float = DEFAULT_LEARNING_SYSTEM_POLICY.zero_value

    @property
    def mean(self) -> float:
        return self.reward_sum / self.n if self.n else DEFAULT_LEARNING_SYSTEM_POLICY.zero_value

    @property
    def ltv_mean(self) -> float:
        return self.ltv_sum / self.n if self.n else DEFAULT_LEARNING_SYSTEM_POLICY.zero_value


class LearningSystem:
    def __init__(self, *, collapse_threshold: float = DEFAULT_LEARNING_SYSTEM_POLICY.default_collapse_threshold, ltv_collapse_threshold: float = DEFAULT_LEARNING_SYSTEM_POLICY.default_ltv_collapse_threshold, ltv_drop_pct: float = DEFAULT_LEARNING_SYSTEM_POLICY.default_ltv_drop_pct, min_samples: int = DEFAULT_LEARNING_SYSTEM_POLICY.default_min_samples, model_registry=None):
        self._stats: dict[str, BanditStats] = {}
        self._collapse_threshold = float(collapse_threshold)
        self._ltv_collapse_threshold = float(ltv_collapse_threshold)
        self._ltv_drop_pct = float(ltv_drop_pct)
        self._last_ltv_mean: dict[str, float] = {}
        self._min_samples = int(min_samples)

        # Optional offline contour: validated candidates are stored here.
        self._model_registry = model_registry

        # last proposal to avoid spamming
        self._last_proposal_hash: str | None = None

    def observe_reward(self, *, policy_id: str, reward: float, ltv: float | None = None) -> None:
        s = self._stats.setdefault(policy_id, BanditStats())
        s.n += 1
        s.reward_sum += float(reward)
        if ltv is not None:
            s.ltv_sum += float(ltv)

    def offline_replay(self, events: Iterable[dict]) -> dict[str, BanditStats]:
        stats: dict[str, BanditStats] = {}
        decision_to_policy: dict[str, str] = {}
        for e in events:
            t = e.get("type")
            if t == "decision_issued":
                decision_to_policy[e["decision_id"]] = e.get("policy_id")
            elif t == "reward_observed":
                did = e.get("decision_id")
                pid = decision_to_policy.get(did)
                if not pid:
                    continue
                s = stats.setdefault(pid, BanditStats())
                s.n += 1
                s.reward_sum += float(e.get("reward") or DEFAULT_LEARNING_SYSTEM_POLICY.zero_value)
        return stats

    def pick_best_policy(self) -> str | None:
        eligible = {pid: st for pid, st in self._stats.items() if st.n >= self._min_samples}
        if not eligible:
            return None
        best = max(eligible.items(), key=lambda kv: kv[1].mean)
        return best[0]

    def maybe_propose_deployment(self) -> dict | None:
        # 0) Prefer offline-validated candidate if present.
        if self._model_registry is not None:
            latest_validated = getattr(self._model_registry, "latest_validated", None)
            if not callable(latest_validated):
                raise RuntimeError("MODEL_REGISTRY_CONTRACT_VIOLATION:latest_validated")
            rec = latest_validated()
            if rec and getattr(rec, "candidate_policy_id", None):
                proposal = {"kind": "deploy", "candidate_policy_id": str(rec.candidate_policy_id), "rollout_pct": DEFAULT_LEARNING_SYSTEM_POLICY.default_rollout_pct}
                ph = str(proposal)
                if ph != self._last_proposal_hash:
                    self._last_proposal_hash = ph
                    return proposal

        # Simple guardrail: propose rollback if current policy collapses
        for pid, st in self._stats.items():
            if st.n >= self._min_samples and st.mean < self._collapse_threshold:
                proposal = {"kind": "rollback", "reason": "reward_collapse"}
                ph = str(proposal)
                if ph != self._last_proposal_hash:
                    self._last_proposal_hash = ph
                    return proposal
                return None

        # Economic guardrail: propose rollback if LTV collapses or drops sharply.
        for pid, st in self._stats.items():
            if st.n >= self._min_samples:
                if st.ltv_mean < self._ltv_collapse_threshold:
                    proposal = {"kind": "rollback", "reason": "ltv_collapse"}
                    ph = str(proposal)
                    if ph != self._last_proposal_hash:
                        self._last_proposal_hash = ph
                        return proposal
                    return None
                prev = self._last_ltv_mean.get(pid)
                if prev is not None and prev > DEFAULT_LEARNING_SYSTEM_POLICY.zero_value and st.ltv_mean < prev * (DEFAULT_LEARNING_SYSTEM_POLICY.unit_value - self._ltv_drop_pct):
                    proposal = {"kind": "rollback", "reason": "ltv_drop"}
                    ph = str(proposal)
                    if ph != self._last_proposal_hash:
                        self._last_proposal_hash = ph
                        return proposal
                    return None
                # update baseline occasionally (after enough samples)
                if st.n % max(self._min_samples, DEFAULT_LEARNING_SYSTEM_POLICY.default_min_samples) == 0:
                    self._last_ltv_mean[pid] = float(st.ltv_mean)
        best = self.pick_best_policy()
        if best is None:
            return None

        # Minimal rollout policy: start at 10% when first time proposing.
        proposal = {"kind": "deploy", "candidate_policy_id": best, "rollout_pct": DEFAULT_LEARNING_SYSTEM_POLICY.default_rollout_pct}
        ph = str(proposal)
        if ph == self._last_proposal_hash:
            return None
        self._last_proposal_hash = ph
        return proposal

    def build_deploy_world_state(self, proposal: dict) -> WorldStateV1:
        # WorldState for deployment decisions is a SYSTEM state.
        return WorldStateV1(
            schema_version=DEFAULT_LEARNING_SYSTEM_POLICY.world_state_schema_version,
            user={"role": DEFAULT_LEARNING_SYSTEM_POLICY.system_role},
            session={},
            product={"name": DEFAULT_LEARNING_SYSTEM_POLICY.workspace_product_name},
            economy={},
            timestamp_ms=int(time.time() * DEFAULT_LEARNING_SYSTEM_POLICY.world_state_timestamp_multiplier),
            tenant_id=current_tenant_id(),
            user_id=DEFAULT_LEARNING_SYSTEM_POLICY.system_user_id,
            safe_mode=DEFAULT_LEARNING_SYSTEM_POLICY.safe_mode_default,
            deployment_proposal=dict(proposal),
        )

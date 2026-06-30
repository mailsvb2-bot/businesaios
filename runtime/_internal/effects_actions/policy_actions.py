"""Sealed effect actions mixin.

This module is INTERNAL to runtime/_internal.
No API changes to EffectsPort.
"""

from __future__ import annotations

from runtime.security.runtime_asserts import assert_called_from_executor

class PolicyEffectsMixin:
    def deploy_policy(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        candidate_policy_id: str,
        rollout_pct: int,
    ) -> bool:
        assert_called_from_executor()
        # Policy deployment is an irreversible action and therefore is executed only via RuntimeExecutor.
        self.policy_registry.set_rollout(candidate_policy_id=str(candidate_policy_id), rollout_pct=int(rollout_pct))
        self.event_log.emit(
            event_type="policy_deployed",
            source="policy_registry",
            user_id="system",
            decision_id=decision_id,
            correlation_id=correlation_id,
            payload={"candidate_policy_id": str(candidate_policy_id), "rollout_pct": int(rollout_pct)},
        )
        return True

    def rollback_policy(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        reason: str,
    ) -> bool:
        assert_called_from_executor()
        self.policy_registry.rollback()
        self.event_log.emit(
            event_type="policy_rolled_back",
            source="policy_registry",
            user_id="system",
            decision_id=decision_id,
            correlation_id=correlation_id,
            payload={"reason": str(reason)},
        )
        return True


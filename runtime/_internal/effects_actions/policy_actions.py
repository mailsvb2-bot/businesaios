"""Sealed governed policy effects.

Policy deployment and rollback mutate one tenant runtime policy registry. The
registry state is snapshotted before mutation and restored exactly when the
audit proof cannot persist.
"""

from __future__ import annotations

from typing import Any

from runtime._internal.effects_tenant import assert_event_log_tenant
from runtime.security.runtime_asserts import assert_called_from_executor


def _policy_evidence(*, code: str, external_ref: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "ledger",
        "verified": True,
        "status": "verified",
        "code": str(code),
        "external_refs": [str(external_ref)],
        "confidence": 1.0,
        "payload": dict(payload),
    }


class PolicyEffectsMixin:
    def deploy_policy(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        tenant_id: str,
        candidate_policy_id: str,
        rollout_pct: int,
    ) -> dict[str, Any]:
        assert_called_from_executor()
        tenant = assert_event_log_tenant(
            self.event_log,
            tenant_id=str(tenant_id),
            operation="deploy_policy",
        )
        payload = {
            "tenant_id": tenant,
            "candidate_policy_id": str(candidate_policy_id),
            "rollout_pct": int(rollout_pct),
        }
        snapshot = self.policy_registry.snapshot_runtime_state()
        try:
            self.policy_registry.set_rollout(
                candidate_policy_id=str(candidate_policy_id),
                rollout_pct=int(rollout_pct),
            )
            self.event_log.emit(
                event_type="policy_deployed",
                source="policy_registry",
                user_id="system",
                decision_id=str(decision_id),
                correlation_id=str(correlation_id),
                payload=payload,
            )
        except Exception:
            self.policy_registry.restore_runtime_state(snapshot)
            raise
        return {
            "ok": True,
            "status": "verified",
            "policy": payload,
            "router_evidence": _policy_evidence(
                code="policy_deployment_recorded",
                external_ref=f"policy-deploy:{tenant}:{decision_id}:{candidate_policy_id}:{int(rollout_pct)}",
                payload=payload,
            ),
        }

    def rollback_policy(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        tenant_id: str,
        reason: str,
    ) -> dict[str, Any]:
        assert_called_from_executor()
        tenant = assert_event_log_tenant(
            self.event_log,
            tenant_id=str(tenant_id),
            operation="rollback_policy",
        )
        payload = {"tenant_id": tenant, "reason": str(reason)}
        snapshot = self.policy_registry.snapshot_runtime_state()
        try:
            self.policy_registry.rollback()
            self.event_log.emit(
                event_type="policy_rolled_back",
                source="policy_registry",
                user_id="system",
                decision_id=str(decision_id),
                correlation_id=str(correlation_id),
                payload=payload,
            )
        except Exception:
            self.policy_registry.restore_runtime_state(snapshot)
            raise
        return {
            "ok": True,
            "status": "verified",
            "rollback": payload,
            "router_evidence": _policy_evidence(
                code="policy_rollback_recorded",
                external_ref=f"policy-rollback:{tenant}:{decision_id}",
                payload=payload,
            ),
        }

from __future__ import annotations

from typing import Any

from config.live_canary_policy import DEFAULT_LIVE_CANARY_POLICY
from core.experiments.guardrails import CanaryDecision, LiveCanaryGuard
from core.experiments.ledger import LiveCanaryLedger
from core.policies.shadow import ShadowDecisionLedger
from core.policies.staged_rollout import RolloutGuard

from runtime._internal.effects_tenant import assert_event_log_tenant
from runtime.security.runtime_asserts import assert_called_from_executor


def _policy_evidence(
    *,
    code: str,
    external_ref: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
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
    def _require_live_canary_evidence(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        candidate_policy_id: str,
        rollout_pct: int,
        experiment_id: str | None,
    ) -> None:
        experiment = str(experiment_id or "").strip()
        if not experiment or int(rollout_pct) <= 0:
            return

        policy = DEFAULT_LIVE_CANARY_POLICY
        if not policy.enabled or policy.experiment_id != experiment:
            raise RuntimeError("LIVE_CANARY_CONFIG_BLOCKED")
        policy.assert_valid()
        if float(rollout_pct) > float(policy.candidate_pct):
            raise RuntimeError("LIVE_CANARY_ROLLOUT_EXCEEDS_CONFIG")

        ledger = LiveCanaryLedger(
            self.event_log,
            experiment_id=experiment,
            candidate_policy_id=str(candidate_policy_id),
        )
        if int(rollout_pct) > int(policy.initial_canary_pct):
            result = LiveCanaryGuard.evaluate(ledger.metrics(), policy)
            if result.decision is not CanaryDecision.PROMOTE:
                raise RuntimeError("LIVE_CANARY_PROMOTION_BLOCKED")

        ledger.record_experiment_created(
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            candidate_pct=float(rollout_pct),
            allowed_actions=policy.allowed_actions,
        )

    def deploy_policy(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        tenant_id: str,
        candidate_policy_id: str,
        rollout_pct: int,
        experiment_id: str | None = None,
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
        if experiment_id:
            payload["experiment_id"] = str(experiment_id)
        if int(rollout_pct) > 0:
            metrics = ShadowDecisionLedger(self.event_log).metrics(
                str(candidate_policy_id)
            )
            if not RolloutGuard.allow_promotion(metrics):
                raise RuntimeError("SHADOW_PROMOTION_BLOCKED")
            self._require_live_canary_evidence(
                decision_id=decision_id,
                correlation_id=correlation_id,
                candidate_policy_id=candidate_policy_id,
                rollout_pct=rollout_pct,
                experiment_id=experiment_id,
            )
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
                external_ref=(
                    f"policy-deploy:{tenant}:{decision_id}:"
                    f"{candidate_policy_id}:{int(rollout_pct)}"
                ),
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

from __future__ import annotations

from dataclasses import replace
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
    ) -> str:
        target_pct = int(rollout_pct)
        if target_pct <= 0:
            return ""

        policy = DEFAULT_LIVE_CANARY_POLICY
        requested_candidate = str(candidate_policy_id or "").strip()
        configured_candidate = str(policy.candidate_policy_id or "").strip()
        if (
            policy.enabled
            and configured_candidate
            and requested_candidate != configured_candidate
        ):
            raise RuntimeError("LIVE_CANARY_CANDIDATE_ID_MISMATCH")
        configured_experiment = policy.experiment_id if policy.enabled else ""
        experiment = str(experiment_id or configured_experiment).strip()
        if policy.enabled and not experiment:
            raise RuntimeError("LIVE_CANARY_EXPERIMENT_REQUIRED")
        if not experiment:
            return ""
        if not policy.enabled or policy.experiment_id != experiment:
            raise RuntimeError("LIVE_CANARY_CONFIG_BLOCKED")
        policy.assert_valid()
        if float(target_pct) > float(policy.max_candidate_pct):
            raise RuntimeError("LIVE_CANARY_ROLLOUT_EXCEEDS_CONFIG")

        ledger = LiveCanaryLedger(
            self.event_log,
            experiment_id=experiment,
            candidate_policy_id=requested_candidate,
            outcome_window_seconds=policy.outcome_window_seconds,
        )
        current_candidate, current_pct_raw = self.policy_registry.rollout_config()
        current_pct = int(current_pct_raw or 0)
        if target_pct > int(policy.initial_canary_pct):
            if (
                str(current_candidate or "") != requested_candidate
                or current_pct <= 0
                or target_pct <= current_pct
            ):
                raise RuntimeError("LIVE_CANARY_STAGE_TRANSITION_BLOCKED")
            evidence_policy = replace(
                policy,
                candidate_pct=float(current_pct),
                max_candidate_pct=max(
                    float(policy.max_candidate_pct),
                    float(current_pct),
                ),
            )
            result = LiveCanaryGuard.evaluate(
                ledger.metrics(candidate_pct=float(current_pct)),
                evidence_policy,
            )
            if result.decision is not CanaryDecision.PROMOTE:
                raise RuntimeError("LIVE_CANARY_PROMOTION_BLOCKED")

        ledger.record_experiment_created(
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            candidate_pct=float(target_pct),
            allowed_actions=policy.allowed_actions,
        )
        return experiment

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
        if int(rollout_pct) > 0:
            metrics = ShadowDecisionLedger(self.event_log).metrics(
                str(candidate_policy_id)
            )
            if not RolloutGuard.allow_promotion(metrics):
                raise RuntimeError("SHADOW_PROMOTION_BLOCKED")
            resolved_experiment = self._require_live_canary_evidence(
                decision_id=decision_id,
                correlation_id=correlation_id,
                candidate_policy_id=candidate_policy_id,
                rollout_pct=rollout_pct,
                experiment_id=experiment_id,
            )
            if resolved_experiment:
                payload["experiment_id"] = resolved_experiment
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

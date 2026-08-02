from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any

from config.live_canary_policy import (
    DEFAULT_LIVE_CANARY_POLICY,
    LiveCanaryPolicy,
)
from core.experiments.assignment import (
    ExperimentArm,
    ExperimentAssignment,
    StableExperimentAssigner,
)
from core.experiments.guardrails import (
    CanaryDecision,
    GuardrailResult,
    LiveCanaryGuard,
)
from core.experiments.ledger import LiveCanaryLedger
from core.experiments.live_canary_events import (
    CANARY_AUTO_ROLLED_BACK,
    CANARY_GUARDRAIL_BREACHED,
)


class LiveCanaryCoordinator:
    """Owns assignment evidence, real outcomes, guardrails, and rollback."""

    def __init__(
        self,
        *,
        event_log: Any,
        policy_registry: Any,
        candidate_policy_id: str,
        policy: LiveCanaryPolicy = DEFAULT_LIVE_CANARY_POLICY,
    ) -> None:
        policy.assert_valid()
        self.policy = policy
        self.event_log = event_log
        self.policy_registry = policy_registry
        self.candidate_policy_id = str(candidate_policy_id)
        self.assigner = StableExperimentAssigner(policy)
        self.ledger = LiveCanaryLedger(
            event_log,
            experiment_id=policy.experiment_id,
            candidate_policy_id=self.candidate_policy_id,
        )

    def assign(
        self,
        *,
        tenant_id: str,
        subject_id: str,
        decision_id: str,
        correlation_id: str | None,
        production_policy_id: str,
        action: str,
        expected_cost: float = 0.0,
    ) -> ExperimentAssignment:
        assignment = self.assigner.assign(
            tenant_id=tenant_id,
            subject_id=subject_id,
            candidate_policy_id=self.candidate_policy_id,
            action=action,
        )
        self.ledger.record_assignment(
            assignment,
            decision_id=decision_id,
            correlation_id=correlation_id,
            production_policy_id=production_policy_id,
            action=action,
            expected_cost=expected_cost,
        )
        return assignment

    def assert_candidate_action_allowed(
        self,
        assignment: ExperimentAssignment,
        *,
        action: str,
    ) -> None:
        if assignment.arm is not ExperimentArm.CANDIDATE:
            return
        if str(action) not in self.policy.allowed_actions:
            raise RuntimeError("LIVE_CANARY_ACTION_BLOCKED")

    def _assignment_payload(self, decision_id: str) -> dict[str, Any]:
        payload = self.ledger.assignment_for_decision(str(decision_id))
        if payload is None or payload.get("eligible") is not True:
            raise RuntimeError("LIVE_CANARY_ASSIGNMENT_REQUIRED")
        return payload

    def record_execution(self, **kwargs: Any) -> dict[str, Any]:
        decision_id = str(kwargs.get("decision_id") or "")
        assignment = self._assignment_payload(decision_id)
        arm = str(getattr(kwargs.get("arm"), "value", kwargs.get("arm")))
        if arm != str(assignment.get("arm") or ""):
            raise RuntimeError("LIVE_CANARY_EXECUTION_ARM_MISMATCH")
        action = str(kwargs.get("action") or "")
        if action != str(assignment.get("action") or ""):
            raise RuntimeError("LIVE_CANARY_EXECUTION_ACTION_MISMATCH")
        if (
            arm == ExperimentArm.CANDIDATE.value
            and action not in self.policy.allowed_actions
        ):
            raise RuntimeError("LIVE_CANARY_ACTION_BLOCKED")
        return self.ledger.record_execution(**kwargs)

    def record_outcome(self, **kwargs: Any) -> dict[str, Any]:
        decision_id = str(kwargs.get("decision_id") or "")
        assignment = self._assignment_payload(decision_id)
        arm = str(getattr(kwargs.get("arm"), "value", kwargs.get("arm")))
        if arm != str(assignment.get("arm") or ""):
            raise RuntimeError("LIVE_CANARY_OUTCOME_ARM_MISMATCH")
        outcome_type = str(kwargs.get("outcome_type") or "")
        if outcome_type not in self.policy.outcome_event_types:
            raise RuntimeError("LIVE_CANARY_OUTCOME_NOT_ALLOWED")
        observed_at_ms = int(
            kwargs.get("observed_at_ms") or time.time() * 1000
        )
        assigned_at_ms = int(assignment.get("assigned_at_ms") or 0)
        deadline_ms = (
            assigned_at_ms + self.policy.outcome_window_seconds * 1000
        )
        if not assigned_at_ms or observed_at_ms > deadline_ms:
            raise RuntimeError("LIVE_CANARY_OUTCOME_WINDOW_EXPIRED")
        kwargs["observed_at_ms"] = observed_at_ms
        return self.ledger.record_outcome(**kwargs)

    def evaluate(self) -> GuardrailResult:
        return LiveCanaryGuard.evaluate(self.ledger.metrics(), self.policy)

    def evaluate_and_maybe_rollback(
        self,
        *,
        decision_id: str,
        correlation_id: str | None,
        tenant_id: str,
    ) -> GuardrailResult:
        try:
            result = self.evaluate()
        except Exception as exc:
            result = GuardrailResult(
                CanaryDecision.ROLLBACK,
                (f"evaluation_error:{exc.__class__.__name__}",),
                {},
            )
        if result.decision is not CanaryDecision.ROLLBACK:
            return result

        payload = {
            "tenant_id": str(tenant_id),
            "experiment_id": self.policy.experiment_id,
            "candidate_policy_id": self.candidate_policy_id,
            "reasons": list(result.reasons),
            "metrics": dict(result.metrics),
        }
        snapshot = self.policy_registry.snapshot_runtime_state()
        try:
            self.policy_registry.set_rollout(
                candidate_policy_id=self.candidate_policy_id,
                rollout_pct=0,
            )
        except Exception:
            self.policy_registry.restore_runtime_state(snapshot)
            raise

        self.event_log.emit(
            event_type=CANARY_GUARDRAIL_BREACHED,
            source="live_canary",
            user_id="system",
            decision_id=str(decision_id),
            correlation_id=correlation_id,
            payload=payload,
        )
        self.event_log.emit(
            event_type=CANARY_AUTO_ROLLED_BACK,
            source="live_canary",
            user_id="system",
            decision_id=str(decision_id),
            correlation_id=correlation_id,
            payload={
                **payload,
                "from_pct": self.policy.candidate_pct,
                "to_pct": 0,
            },
        )
        return result

    def evidence(self) -> dict[str, Any]:
        result = self.evaluate()
        return {
            "experiment_id": self.policy.experiment_id,
            "candidate_policy_id": self.candidate_policy_id,
            "decision": result.decision.value,
            "reasons": list(result.reasons),
            "metrics": dict(result.metrics),
            "statistics": (
                asdict(result.statistics) if result.statistics else None
            ),
        }


__all__ = ["LiveCanaryCoordinator"]

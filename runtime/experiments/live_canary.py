from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import asdict, replace
from collections.abc import Mapping
from threading import Lock
from typing import Any

from config.live_canary_policy import (
    DEFAULT_LIVE_CANARY_POLICY,
    LiveCanaryPolicy,
)
from runtime.proofs import ACTION_PROOF_EVENT
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


def _event_data(event: Any) -> dict[str, Any]:
    return event if isinstance(event, dict) else vars(event)


def _event_payload(event: Any) -> dict[str, Any]:
    return dict(_event_data(event).get("payload") or {})


def _finite(value: object, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def source_event_evidence_ref(event: Any) -> str:
    data = _event_data(event)
    payload = _event_payload(event)
    for source in (data, payload):
        for key in ("event_id", "id", "external_id"):
            value = source.get(key) if isinstance(source, Mapping) else None
            if value is not None and str(value).strip():
                return f"event:{str(value).strip()}"
    digest = hashlib.sha256(
        json.dumps(
            data, sort_keys=True, separators=(",", ":"), default=str
        ).encode("utf-8")
    ).hexdigest()
    return f"event-sha256:{digest}"


class LiveCanaryCoordinator:
    """Own assignment evidence and pure guard evaluation.

    Registry mutation is intentionally confined to `evaluate_and_maybe_rollback`,
    which is called from the RuntimeExecutor execution stack. Decision-time and
    webhook-time checks only open the local circuit and emit evidence.
    """

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
        self.ledger = LiveCanaryLedger(
            event_log,
            experiment_id=policy.experiment_id,
            candidate_policy_id=self.candidate_policy_id,
            outcome_window_seconds=policy.outcome_window_seconds,
        )
        self._assignment_lock = Lock()
        self._rollback_required = False

    @property
    def rollback_required(self) -> bool:
        return bool(self._rollback_required)

    def live_rollout_pct(self) -> float:
        getter = getattr(self.policy_registry, "rollout_config", None)
        if callable(getter):
            candidate_policy_id, rollout_pct = getter()
            if str(candidate_policy_id or "") != self.candidate_policy_id:
                return 0.0
            return max(0.0, min(100.0, _finite(rollout_pct)))
        return max(0.0, min(100.0, float(self.policy.candidate_pct)))

    def _effective_policy(self) -> LiveCanaryPolicy:
        current_pct = self.live_rollout_pct()
        if current_pct <= 0:
            raise RuntimeError("LIVE_CANARY_ROLLOUT_INACTIVE")
        return replace(
            self.policy,
            candidate_pct=current_pct,
            max_candidate_pct=max(
                float(self.policy.max_candidate_pct),
                current_pct,
            ),
        )

    def _guard_result(self) -> GuardrailResult:
        if self.live_rollout_pct() <= 0:
            return GuardrailResult(
                CanaryDecision.CONTINUE,
                ("rollout_inactive",),
                {},
            )
        try:
            return self.evaluate()
        except Exception as exc:
            return GuardrailResult(
                CanaryDecision.ROLLBACK,
                (f"evaluation_error:{exc.__class__.__name__}",),
                {},
            )

    def _open_local_circuit(
        self,
        result: GuardrailResult,
        *,
        decision_id: str,
        correlation_id: str | None,
        tenant_id: str,
    ) -> None:
        self._rollback_required = True
        try:
            self.event_log.emit(
                event_type=CANARY_GUARDRAIL_BREACHED,
                source="live_canary",
                user_id="system",
                decision_id=str(decision_id),
                correlation_id=correlation_id,
                payload={
                    "tenant_id": str(tenant_id),
                    "experiment_id": self.policy.experiment_id,
                    "candidate_policy_id": self.candidate_policy_id,
                    "reasons": list(result.reasons),
                    "metrics": dict(result.metrics),
                    "rollback_required": True,
                },
            )
        except Exception:
            return

    def assign(
        self,
        *,
        tenant_id: str,
        subject_id: str,
        decision_id: str,
        correlation_id: str | None,
        production_policy_id: str,
        action: str,
        purpose: str,
        eligible: bool,
        expected_cost: float = 0.0,
    ) -> ExperimentAssignment:
        with self._assignment_lock:
            effective = self._effective_policy()
            assignment = StableExperimentAssigner(effective).assign(
                tenant_id=tenant_id,
                subject_id=subject_id,
                candidate_policy_id=self.candidate_policy_id,
                action=action,
                purpose=purpose,
                eligible=eligible,
            )
            if (
                assignment.arm is ExperimentArm.CANDIDATE
                and self._rollback_required
            ):
                raise RuntimeError("LIVE_CANARY_ROLLBACK_PENDING")
            self.ledger.record_assignment(
                assignment,
                decision_id=decision_id,
                correlation_id=correlation_id,
                production_policy_id=production_policy_id,
                action=action,
                candidate_pct=effective.candidate_pct,
                expected_cost=expected_cost,
            )
            if assignment.eligible:
                guard = self._guard_result()
                if guard.decision is CanaryDecision.ROLLBACK:
                    self._open_local_circuit(
                        guard,
                        decision_id=f"assignment-guard:{decision_id}",
                        correlation_id=correlation_id,
                        tenant_id=assignment.tenant_id,
                    )
                    if assignment.arm is ExperimentArm.CANDIDATE:
                        raise RuntimeError("LIVE_CANARY_ASSIGNMENT_GUARD_BLOCKED")
            return assignment

    def assert_candidate_action_allowed(
        self,
        assignment: ExperimentAssignment,
        *,
        action: str,
    ) -> None:
        if assignment.arm is not ExperimentArm.CANDIDATE:
            return
        if self._rollback_required:
            raise RuntimeError("LIVE_CANARY_ROLLBACK_PENDING")
        if str(action) not in self.policy.allowed_actions:
            raise RuntimeError("LIVE_CANARY_ACTION_BLOCKED")

    def _assignment_payload(self, decision_id: str) -> dict[str, Any]:
        payload = self.ledger.assignment_for_decision(str(decision_id))
        if payload is None or payload.get("eligible") is not True:
            raise RuntimeError("LIVE_CANARY_ASSIGNMENT_REQUIRED")
        return payload

    def _verified_source_event(
        self,
        *,
        decision_id: str,
        event_type: str,
        success: bool,
        evidence_ref: str | None = None,
    ) -> dict[str, Any]:
        events = self.ledger.events_for_decision(decision_id, event_type)
        for event in reversed(events):
            data = _event_data(event)
            if str(data.get("source") or "") == "live_canary":
                continue
            payload = _event_payload(event)
            meta = payload.get("meta")
            if isinstance(meta, dict) and str(meta.get("mode") or "") == "stub":
                continue
            observed = payload.get("ok")
            if observed is None:
                observed = payload.get("success")
            if observed is not bool(success):
                continue
            if evidence_ref and source_event_evidence_ref(event) != evidence_ref:
                continue
            return payload
        raise RuntimeError("LIVE_CANARY_VERIFIED_SOURCE_EVENT_REQUIRED")

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

        ok = bool(kwargs.get("ok"))
        proof_event_type = str(kwargs.get("proof_event_type") or "")
        expected_proof = ACTION_PROOF_EVENT.get(action)
        if ok and (not expected_proof or proof_event_type != expected_proof):
            raise RuntimeError("LIVE_CANARY_ACTION_PROOF_TYPE_MISMATCH")
        proof_payload = self._verified_source_event(
            decision_id=decision_id,
            event_type=proof_event_type,
            success=ok,
        )
        assigned_at_ms = int(assignment.get("assigned_at_ms") or 0)
        executed_at_ms = int(
            kwargs.get("executed_at_ms") or time.time() * 1000
        )
        if not assigned_at_ms or executed_at_ms < assigned_at_ms:
            raise RuntimeError("LIVE_CANARY_EXECUTION_PRECEDES_ASSIGNMENT")
        kwargs["executed_at_ms"] = executed_at_ms
        kwargs["cost"] = max(
            _finite(kwargs.get("cost")),
            _finite(proof_payload.get("cost")),
        )
        kwargs["critical_violation"] = bool(
            kwargs.get("critical_violation")
            or proof_payload.get("critical_violation")
        )
        kwargs["complaint"] = bool(
            kwargs.get("complaint") or proof_payload.get("complaint")
        )
        return self.ledger.record_execution(**kwargs)

    def record_outcome(self, **kwargs: Any) -> dict[str, Any]:
        decision_id = str(kwargs.get("decision_id") or "")
        correlation_id = kwargs.get("correlation_id")
        assignment = self._assignment_payload(decision_id)
        arm = str(getattr(kwargs.get("arm"), "value", kwargs.get("arm")))
        if arm != str(assignment.get("arm") or ""):
            raise RuntimeError("LIVE_CANARY_OUTCOME_ARM_MISMATCH")
        outcome_type = str(kwargs.get("outcome_type") or "")
        if outcome_type not in self.policy.outcome_event_types:
            raise RuntimeError("LIVE_CANARY_OUTCOME_NOT_ALLOWED")
        success = bool(kwargs.get("success"))
        evidence_ref = str(kwargs.get("evidence_ref") or "")
        if not evidence_ref.startswith(("event:", "event-sha256:")):
            raise RuntimeError("LIVE_CANARY_CANONICAL_EVIDENCE_REF_REQUIRED")
        source_payload = self._verified_source_event(
            decision_id=decision_id,
            event_type=outcome_type,
            success=success,
            evidence_ref=evidence_ref,
        )
        observed_at_ms = int(
            kwargs.get("observed_at_ms") or time.time() * 1000
        )
        assigned_at_ms = int(assignment.get("assigned_at_ms") or 0)
        deadline_ms = (
            assigned_at_ms + self.policy.outcome_window_seconds * 1000
        )
        if not assigned_at_ms or observed_at_ms < assigned_at_ms:
            raise RuntimeError("LIVE_CANARY_OUTCOME_PRECEDES_ASSIGNMENT")
        if observed_at_ms > deadline_ms:
            raise RuntimeError("LIVE_CANARY_OUTCOME_WINDOW_EXPIRED")
        kwargs["observed_at_ms"] = observed_at_ms
        kwargs["value"] = _finite(
            source_payload.get("value", source_payload.get("amount", 0.0))
        )
        kwargs["revenue"] = _finite(
            source_payload.get(
                "revenue",
                source_payload.get("amount", source_payload.get("value", 0.0)),
            )
        )
        recorded = self.ledger.record_outcome(**kwargs)
        guard = self._guard_result()
        if guard.decision is CanaryDecision.ROLLBACK:
            self._open_local_circuit(
                guard,
                decision_id=f"outcome-guard:{decision_id}",
                correlation_id=correlation_id,
                tenant_id=str(assignment.get("tenant_id") or ""),
            )
        return recorded

    def evaluate(self) -> GuardrailResult:
        effective = self._effective_policy()
        metrics = self.ledger.metrics(candidate_pct=effective.candidate_pct)
        return LiveCanaryGuard.evaluate(metrics, effective)

    def evaluate_and_maybe_rollback(
        self,
        *,
        decision_id: str,
        correlation_id: str | None,
        tenant_id: str,
    ) -> GuardrailResult:
        """Executor-side emergency rollback path."""

        from_pct = self.live_rollout_pct()
        result = self._guard_result()
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
        self._rollback_required = False

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
            payload={**payload, "from_pct": from_pct, "to_pct": 0},
        )
        return result

    def evidence(self) -> dict[str, Any]:
        result = self._guard_result()
        return {
            "experiment_id": self.policy.experiment_id,
            "candidate_policy_id": self.candidate_policy_id,
            "rollout_pct": self.live_rollout_pct(),
            "rollback_required": self.rollback_required,
            "decision": result.decision.value,
            "reasons": list(result.reasons),
            "metrics": dict(result.metrics),
            "statistics": (
                asdict(result.statistics) if result.statistics else None
            ),
        }


__all__ = ["LiveCanaryCoordinator", "source_event_evidence_ref"]

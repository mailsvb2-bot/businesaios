from __future__ import annotations

from execution.runtime_keys import ACTION_BUDGET_KEY, KILL_SWITCH_KEY
from dataclasses import dataclass
from typing import Any, Mapping

from execution.action_budget_engine import ActionBudgetEngine
from execution.canonical_autonomy_safety import canonical_autonomy_safety_decision
from execution.autonomy_audit import AutonomyAuditRecord
from execution.autonomy_counters import AutonomyCounterResolver
from application.autonomy.autonomy_kill_switch import FileAutonomyKillSwitchRegistry
from application.autonomy.autonomy_tiers import evaluate_autonomy_tier
from execution.blast_radius_guard import BlastRadiusGuard
from execution.bounded_autonomy import BoundedAutonomyGuard
from execution.safe_self_driving import SafeSelfDrivingPolicy


CANON_AUTONOMY_SAFETY_BUNDLE = True


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _text(value: object) -> str:
    return str(value or "").strip()


@dataclass(frozen=True)
class AutonomySafetyVerdict:
    allowed: bool
    operator_required: bool
    reason: str
    details: dict[str, Any]
    next_tier: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": bool(self.allowed),
            "operator_required": bool(self.operator_required),
            "reason": str(self.reason),
            "details": dict(self.details),
            "next_tier": str(self.next_tier),
        }


class AutonomySafetyBundle:
    def __init__(
        self,
        *,
        action_budget_engine: ActionBudgetEngine | None = None,
        blast_radius_guard: BlastRadiusGuard | None = None,
        bounded_autonomy_guard: BoundedAutonomyGuard | None = None,
        safe_self_driving_policy: SafeSelfDrivingPolicy | None = None,
        counter_resolver: AutonomyCounterResolver | None = None,
        kill_switch_registry: FileAutonomyKillSwitchRegistry | None = None,
    ) -> None:
        self._action_budget_engine = action_budget_engine or ActionBudgetEngine()
        self._blast_radius_guard = blast_radius_guard or BlastRadiusGuard(action_budget_engine=self._action_budget_engine)
        self._bounded_autonomy_guard = bounded_autonomy_guard or BoundedAutonomyGuard(action_budget_engine=self._action_budget_engine)
        self._safe_self_driving_policy = safe_self_driving_policy or SafeSelfDrivingPolicy()
        self._counter_resolver = counter_resolver or AutonomyCounterResolver()
        self._kill_switch_registry = kill_switch_registry

    def evaluate_pre_execution(
        self,
        *,
        request: Any,
        action_type: str,
        payload: Mapping[str, Any] | None,
        previous_feedback: Mapping[str, Any] | None,
        event_log: Any | None,
        recent_actions: list[dict[str, Any]] | None,
    ) -> AutonomySafetyVerdict:
        tier_decision = evaluate_autonomy_tier(
            action_type=action_type,
            autonomy_tier=getattr(request, "autonomy_tier", "supervised"),
            approval_policy=dict(getattr(request, "approval_policy", {}) or {}),
        )
        payload_dict = dict(payload or {})
        tenant_id = _text(getattr(request, "tenant_id", "default") or payload_dict.get("tenant_id") or "default")
        business_id = _text(getattr(request, "business_id", "default") or payload_dict.get("business_id") or "default")
        domain = _text(payload_dict.get("domain") or payload_dict.get("integration_domain") or tier_decision.action_class or "default")
        if self._kill_switch_registry is not None:
            kill = self._kill_switch_registry.evaluate(tenant_id=tenant_id, business_id=business_id, integration_domain=domain, action_type=_text(action_type))
            if kill.active:
                return AutonomySafetyVerdict(False, True, "kill_switch_active", {KILL_SWITCH_KEY: kill.to_dict()}, getattr(request, "autonomy_tier", "supervised"))
        if tier_decision.blocked_by_policy or tier_decision.approval_required:
            return AutonomySafetyVerdict(
                False,
                bool(tier_decision.approval_required or tier_decision.blocked_by_policy),
                tier_decision.handoff_reason or "autonomy_tier_denied",
                {"autonomy_tier": tier_decision.__dict__},
                getattr(request, "autonomy_tier", "supervised"),
            )
        budget = self._action_budget_engine.evaluate(
            request=request,
            action_type=action_type,
            payload=payload_dict,
            previous_feedback=previous_feedback,
        )
        if not budget.allowed:
            return AutonomySafetyVerdict(False, True, str(budget.reason), {ACTION_BUDGET_KEY: budget.to_dict()}, getattr(request, "autonomy_tier", "supervised"))
        bounded = self._bounded_autonomy_guard.evaluate(
            request=request,
            action_type=action_type,
            payload=payload_dict,
            previous_feedback=previous_feedback,
            budget_decision=budget,
        )
        if not bounded.allowed:
            return AutonomySafetyVerdict(False, bool(bounded.operator_required), str(bounded.reason), {"bounded_autonomy": bounded.to_dict(), ACTION_BUDGET_KEY: budget.to_dict()}, getattr(request, "autonomy_tier", "supervised"))
        counters = self._counter_resolver.resolve(
            tenant_id=tenant_id,
            business_id=business_id,
            event_log=event_log,
            recent_actions=list(recent_actions or []),
            action_type=action_type,
        )
        blast = self._blast_radius_guard.evaluate(
            request=request,
            action_type=action_type,
            payload={**payload_dict, "persistent_counters": counters.to_dict()},
            event_log=event_log,
            tenant_id=tenant_id,
            autonomy_tier=getattr(request, "autonomy_tier", "supervised"),
            recent_actions=list(recent_actions or []),
        )
        if not blast.allowed:
            return AutonomySafetyVerdict(False, True, str(blast.reason or "blast_radius_exceeded"), {"blast_radius_guard": {"allowed": False, "reason": blast.reason, "details": dict(blast.details or {})}, "persistent_counters": counters.to_dict(), "bounded_autonomy": bounded.to_dict(), ACTION_BUDGET_KEY: budget.to_dict()}, getattr(request, "autonomy_tier", "supervised"))
        return AutonomySafetyVerdict(True, False, "within_autonomy_safety_bundle", {"autonomy_tier": tier_decision.__dict__, ACTION_BUDGET_KEY: budget.to_dict(), "bounded_autonomy": bounded.to_dict(), "blast_radius_guard": {"allowed": True, "reason": blast.reason, "details": dict(blast.details or {})}, "persistent_counters": counters.to_dict()}, getattr(request, "autonomy_tier", "supervised"))

    def evaluate_post_step(
        self,
        *,
        request: Any,
        steps: list[Any],
        previous_feedback: Mapping[str, Any] | None,
        last_step: Any,
        consecutive_failures: int,
    ) -> AutonomySafetyVerdict:
        safe_loop = self._safe_self_driving_policy.evaluate(
            request=request,
            steps=steps,
            previous_feedback=previous_feedback,
            last_step=last_step,
            consecutive_failures=consecutive_failures,
        )
        return AutonomySafetyVerdict(
            allowed=not bool(safe_loop.should_stop),
            operator_required=bool(getattr(last_step, "operator_required", False) or safe_loop.should_stop),
            reason=str(safe_loop.reason),
            details={"safe_self_driving": safe_loop.to_dict()},
            next_tier=str(safe_loop.next_tier),
        )

    @staticmethod
    def build_policy_snapshot(*, request: Any, safety_verdict: Mapping[str, Any] | None) -> dict[str, Any]:
        verdict = _safe_dict(safety_verdict)
        return {
            "autonomy_tier": _text(getattr(request, "autonomy_tier", "supervised") or "supervised"),
            "approval_policy": dict(getattr(request, "approval_policy", {}) or {}),
            "constraints": dict(getattr(request, "constraints", {}) or {}),
            "economy": dict(getattr(request, "economy", {}) or {}),
            "safety_verdict": verdict,
            "bounded_autonomy": dict(_safe_dict(verdict.get("details")).get("bounded_autonomy") or {}),
            "blast_radius_guard": dict(_safe_dict(verdict.get("details")).get("blast_radius_guard") or {}),
            ACTION_BUDGET_KEY: dict(_safe_dict(verdict.get("details")).get(ACTION_BUDGET_KEY) or {}),
            "persistent_counters": dict(_safe_dict(verdict.get("details")).get("persistent_counters") or {}),
            "autonomy_safety_decision": canonical_autonomy_safety_decision(
                request=request,
                safety_verdict=verdict,
            ),
        }

    @staticmethod
    def build_audit_record(*, request: Any, verdict: Mapping[str, Any], runtime_verdict_matched: bool | None = None) -> AutonomyAuditRecord:
        details = _safe_dict(_safe_dict(verdict).get("details"))
        violated_limits = tuple(
            list(_safe_dict(details.get("bounded_autonomy") or {}).get("violated_limits") or [])
            + list(_safe_dict(_safe_dict(details.get("blast_radius_guard") or {}).get("details")).get("violated_limits") or [])
            + list(_safe_dict(details.get(ACTION_BUDGET_KEY) or {}).get("violated_limits") or [])
        )
        return AutonomyAuditRecord(
            tier_at_decision_time=_text(getattr(request, "autonomy_tier", "supervised") or "supervised"),
            safety_verdict=_text(_safe_dict(verdict).get("reason") or "unknown"),
            violated_limits=tuple(dict.fromkeys(violated_limits)),
            next_tier_decision=_text(_safe_dict(verdict).get("next_tier") or getattr(request, "autonomy_tier", "supervised")),
            handoff_reason=_text(_safe_dict(verdict).get("reason") or "") or None,
            runtime_verdict_matched=runtime_verdict_matched,
        )


__all__ = ["AutonomySafetyBundle", "AutonomySafetyVerdict", "CANON_AUTONOMY_SAFETY_BUNDLE"]

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from application.business_autonomy.contracts import BusinessExecutionRequest
from application.business_autonomy.safety_core import SafetyRuntimePolicy, validate_blast_radius, validate_budget


@dataclass(frozen=True)
class BudgetGuardDecision:
    allowed: bool
    reason: str
    budget_limit: float | None = None
    estimated_cost: float | None = None
    safety_verdict: dict[str, object] | None = None


class BusinessBudgetGuard:
    def __init__(self, max_budget_minor: int | float | None = None) -> None:
        self.max_budget_minor = max_budget_minor

    def evaluate(self, request: BusinessExecutionRequest) -> BudgetGuardDecision:
        estimated_cost = _float_or_zero(request.envelope.goal_payload.get("estimated_cost", 0.0))
        budget_limit = _extract_float_constraint(request, "monthly_budget_limit")
        if budget_limit is None and self.max_budget_minor is not None:
            budget_limit = _float_or_none(self.max_budget_minor)
        policy = SafetyRuntimePolicy.from_metadata(request.envelope.metadata)
        if budget_limit is None:
            if policy.mode == "strict_rust_required" and not policy.rust_available:
                safety = validate_budget(estimated_minor=0, limit_minor=0, policy=policy)
                return BudgetGuardDecision(False, f"Budget safety denied: {safety.reason}", None, estimated_cost, safety.to_metadata())
            verdict = {"allowed": True, "reason": "budget_limit_not_configured", "source": "python_safety_core"}
            return BudgetGuardDecision(True, "No explicit budget limit provided.", None, estimated_cost, verdict)
        safety = validate_budget(
            estimated_minor=_money_to_minor(estimated_cost),
            limit_minor=_money_to_minor(budget_limit),
            currency=str(request.envelope.metadata.get("currency") or "RUB"),
            limit_currency=str(request.envelope.metadata.get("budget_currency") or request.envelope.metadata.get("currency") or "RUB"),
            policy=policy,
        )
        if not safety.allowed:
            reason = "Estimated cost exceeds approved budget limit." if safety.reason == "budget_exceeded" else f"Budget safety denied: {safety.reason}"
            return BudgetGuardDecision(False, reason, budget_limit, estimated_cost, safety.to_metadata())
        return BudgetGuardDecision(True, "Estimated cost is within budget limit.", budget_limit, estimated_cost, safety.to_metadata())


@dataclass(frozen=True)
class BlastRadiusDecision:
    allowed: bool
    reason: str
    outbound_limit: int | None = None
    requested_outbound: int | None = None
    safety_verdict: dict[str, object] | None = None


class BusinessBlastRadiusGuard:
    def __init__(self, max_parallel_actions: int | None = None) -> None:
        self.max_parallel_actions = max_parallel_actions

    def evaluate(self, request: BusinessExecutionRequest) -> BlastRadiusDecision:
        requested = _int_or_default(request.envelope.goal_payload.get("outbound_count", 1), 1)
        limit = _extract_int_constraint(request, "outbound_message_limit")
        if limit is None and self.max_parallel_actions is not None:
            limit = _int_or_none(self.max_parallel_actions)
        policy = SafetyRuntimePolicy.from_metadata(request.envelope.metadata)
        if limit is None:
            if policy.mode == "strict_rust_required" and not policy.rust_available:
                safety = validate_blast_radius(requested_outbound=1, approved_limit=1, policy=policy)
                return BlastRadiusDecision(False, f"Blast radius safety denied: {safety.reason}", None, requested, safety.to_metadata())
            verdict = {"allowed": True, "reason": "blast_radius_limit_not_configured", "source": "python_safety_core"}
            return BlastRadiusDecision(True, "No explicit outbound blast radius limit provided.", None, requested, verdict)
        safety = validate_blast_radius(requested_outbound=requested, approved_limit=limit, policy=policy)
        if not safety.allowed:
            reason = "Requested outbound scope exceeds blast radius limit." if safety.reason == "blast_radius_exceeded" else f"Blast radius safety denied: {safety.reason}"
            return BlastRadiusDecision(False, reason, limit, requested, safety.to_metadata())
        return BlastRadiusDecision(True, "Requested outbound scope is within blast radius limit.", limit, requested, safety.to_metadata())


class ApprovalStatus(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    NOT_REQUIRED = "not_required"
    PENDING = "pending"


@dataclass(frozen=True)
class ApprovalDecision:
    status: ApprovalStatus
    reason: str
    approver_id: str | None = None


class BusinessApprovalGate:
    def evaluate(self, *, request: BusinessExecutionRequest, requires_approval: bool) -> ApprovalDecision:
        explicit_constraint_requires_approval = any(
            item.name == "require_human_approval" and bool(item.value) is True
            for item in request.envelope.constraints
        )
        if not requires_approval and not explicit_constraint_requires_approval:
            return ApprovalDecision(ApprovalStatus.NOT_REQUIRED, "Approval is not required.")
        approved_by = request.envelope.metadata.get("approved_by")
        if approved_by:
            return ApprovalDecision(ApprovalStatus.APPROVED, "Approval provided.", str(approved_by))
        return ApprovalDecision(ApprovalStatus.PENDING, "Approval required but not yet provided.")


class OperatorOverrideMode(str, Enum):
    NONE = "none"
    FORCE_ALLOW = "force_allow"
    FORCE_DENY = "force_deny"
    FORCE_SIMULATION = "force_simulation"


@dataclass(frozen=True)
class OperatorOverrideDecision:
    mode: OperatorOverrideMode
    reason: str
    operator_id: str | None = None


class BusinessOperatorOverridePolicy:
    def evaluate(self, request: BusinessExecutionRequest) -> OperatorOverrideDecision:
        metadata = request.envelope.metadata
        raw_mode = metadata.get("operator_override_mode")
        if raw_mode is None:
            return OperatorOverrideDecision(OperatorOverrideMode.NONE, "No operator override requested.")
        return OperatorOverrideDecision(
            mode=OperatorOverrideMode(str(raw_mode)),
            reason=str(metadata.get("operator_override_reason", "operator override")),
            operator_id=str(metadata.get("operator_id")) if metadata.get("operator_id") is not None else None,
        )


@dataclass(frozen=True)
class IdempotencyRecord:
    key: str
    payload: object


class BusinessIdempotencyStore:
    def __init__(self) -> None:
        self._items: dict[str, IdempotencyRecord] = {}

    def get(self, key: str):
        record = self._items.get(key)
        return None if record is None else record.payload

    def put(self, key: str, payload: object) -> None:
        self._items[key] = IdempotencyRecord(key=key, payload=payload)


def _extract_float_constraint(request: BusinessExecutionRequest, name: str) -> float | None:
    for item in request.envelope.constraints:
        if item.name == name:
            return _float_or_none(item.value)
    return None


def _extract_int_constraint(request: BusinessExecutionRequest, name: str) -> int | None:
    for item in request.envelope.constraints:
        if item.name == name:
            return _int_or_none(item.value)
    return None


def _float_or_zero(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _float_or_none(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_default(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _int_or_none(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _money_to_minor(value: float) -> int:
    return int(round(float(value) * 100))

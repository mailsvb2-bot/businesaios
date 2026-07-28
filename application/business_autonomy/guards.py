from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from threading import RLock

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
    """Prove that a DecisionCore-selected paid action fits an explicit budget."""

    def __init__(self, max_budget_minor: int | float | None = None) -> None:
        self.max_budget_minor = max_budget_minor

    def evaluate(self, request: BusinessExecutionRequest) -> BudgetGuardDecision:
        raw_estimated = request.envelope.goal_payload.get("estimated_cost", 0.0)
        estimated_cost = _finite_float_or_none(raw_estimated)
        if estimated_cost is None or estimated_cost < 0:
            verdict = {"allowed": False, "reason": "invalid_estimated_cost", "source": "python_safety_core"}
            return BudgetGuardDecision(False, "Estimated cost must be a finite non-negative number.", None, None, verdict)

        budget_limit = _extract_float_constraint(request, "monthly_budget_limit")
        if budget_limit is None and self.max_budget_minor is not None:
            configured_minor = _finite_float_or_none(self.max_budget_minor)
            if configured_minor is None or configured_minor < 0:
                verdict = {"allowed": False, "reason": "invalid_configured_budget_limit", "source": "python_safety_core"}
                return BudgetGuardDecision(False, "Configured budget limit is invalid.", None, estimated_cost, verdict)
            budget_limit = configured_minor / 100.0

        policy = SafetyRuntimePolicy.from_metadata(request.envelope.metadata)
        if budget_limit is None:
            if _requires_explicit_budget(request=request, estimated_cost=estimated_cost):
                verdict = {"allowed": False, "reason": "budget_limit_required", "source": "python_safety_core"}
                return BudgetGuardDecision(False, "Paid execution requires an explicit budget limit.", None, estimated_cost, verdict)
            if policy.mode == "strict_rust_required" and not policy.rust_available:
                safety = validate_budget(estimated_minor=0, limit_minor=0, policy=policy)
                return BudgetGuardDecision(False, f"Budget safety denied: {safety.reason}", None, estimated_cost, safety.to_metadata())
            verdict = {"allowed": True, "reason": "budget_not_applicable", "source": "python_safety_core"}
            return BudgetGuardDecision(True, "No paid execution is requested.", None, estimated_cost, verdict)

        if budget_limit < 0 or not math.isfinite(budget_limit):
            verdict = {"allowed": False, "reason": "invalid_budget_limit", "source": "python_safety_core"}
            return BudgetGuardDecision(False, "Budget limit must be a finite non-negative number.", budget_limit, estimated_cost, verdict)

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
    """Prove that a DecisionCore-selected external write has bounded fan-out."""

    def __init__(self, max_parallel_actions: int | None = None) -> None:
        self.max_parallel_actions = max_parallel_actions

    def evaluate(self, request: BusinessExecutionRequest) -> BlastRadiusDecision:
        raw_requested = request.envelope.goal_payload.get("outbound_count", 1)
        requested = _strict_int_or_none(raw_requested)
        if requested is None or requested < 0:
            verdict = {"allowed": False, "reason": "invalid_outbound_count", "source": "python_safety_core"}
            return BlastRadiusDecision(False, "Outbound count must be a non-negative integer.", None, None, verdict)

        limit = _extract_int_constraint(request, "outbound_message_limit")
        if limit is None and self.max_parallel_actions is not None:
            limit = _strict_int_or_none(self.max_parallel_actions)

        policy = SafetyRuntimePolicy.from_metadata(request.envelope.metadata)
        if limit is None:
            if _requires_explicit_blast_limit(request=request, requested=requested):
                verdict = {"allowed": False, "reason": "blast_radius_limit_required", "source": "python_safety_core"}
                return BlastRadiusDecision(False, "External write execution requires an explicit blast-radius limit.", None, requested, verdict)
            if policy.mode == "strict_rust_required" and not policy.rust_available:
                safety = validate_blast_radius(requested_outbound=1, approved_limit=1, policy=policy)
                return BlastRadiusDecision(False, f"Blast radius safety denied: {safety.reason}", None, requested, safety.to_metadata())
            verdict = {"allowed": True, "reason": "blast_radius_not_applicable", "source": "python_safety_core"}
            return BlastRadiusDecision(True, "No external fan-out is requested.", None, requested, verdict)

        if limit <= 0:
            verdict = {"allowed": False, "reason": "invalid_blast_radius_limit", "source": "python_safety_core"}
            return BlastRadiusDecision(False, "Blast-radius limit must be a positive integer.", limit, requested, verdict)

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
    """Compatibility gate that never accepts approval claims from request metadata."""

    def evaluate(self, *, request: BusinessExecutionRequest, requires_approval: bool) -> ApprovalDecision:
        explicit_constraint_requires_approval = any(
            item.name == "require_human_approval" and bool(item.value) is True
            for item in request.envelope.constraints
        )
        if not requires_approval and not explicit_constraint_requires_approval:
            return ApprovalDecision(ApprovalStatus.NOT_REQUIRED, "Approval is not required.")
        return ApprovalDecision(ApprovalStatus.PENDING, "Approval must be recorded by the canonical governance store.")


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
    override_id: str | None = None


class BusinessOperatorOverridePolicy:
    """Compatibility policy that rejects request-supplied override claims."""

    def evaluate(self, request: BusinessExecutionRequest) -> OperatorOverrideDecision:
        del request
        return OperatorOverrideDecision(OperatorOverrideMode.NONE, "No canonical operator override is recorded.")


class BusinessIdempotencyReservationStatus(str, Enum):
    ACCEPTED = "accepted"
    REPLAY_COMPLETED = "replay_completed"
    IN_PROGRESS = "in_progress"
    TERMINAL_FAILED = "terminal_failed"


@dataclass(frozen=True)
class BusinessIdempotencyReservation:
    status: BusinessIdempotencyReservationStatus
    payload: object | None = None


@dataclass
class _BusinessIdempotencyRecord:
    owner_id: str
    state: str
    payload: object | None = None
    failure_reason: str | None = None


class BusinessIdempotencyStore:
    """Process-local compatibility store with reserve-before-effect semantics."""

    def __init__(self) -> None:
        self._items: dict[str, _BusinessIdempotencyRecord] = {}
        self._lock = RLock()

    def get(self, key: str):
        with self._lock:
            record = self._items.get(str(key))
            if record is None or record.state != "completed":
                return None
            return record.payload

    def reserve(self, key: str, *, owner_id: str) -> BusinessIdempotencyReservation:
        normalized_key = str(key).strip()
        normalized_owner = str(owner_id).strip()
        if not normalized_key:
            raise ValueError("idempotency key is required")
        if not normalized_owner:
            raise ValueError("idempotency owner is required")
        with self._lock:
            current = self._items.get(normalized_key)
            if current is None:
                self._items[normalized_key] = _BusinessIdempotencyRecord(owner_id=normalized_owner, state="in_progress")
                return BusinessIdempotencyReservation(BusinessIdempotencyReservationStatus.ACCEPTED)
            if current.state == "completed":
                return BusinessIdempotencyReservation(BusinessIdempotencyReservationStatus.REPLAY_COMPLETED, current.payload)
            if current.state == "failed":
                return BusinessIdempotencyReservation(BusinessIdempotencyReservationStatus.TERMINAL_FAILED)
            return BusinessIdempotencyReservation(BusinessIdempotencyReservationStatus.IN_PROGRESS)

    def complete(self, key: str, *, owner_id: str, payload: object) -> None:
        with self._lock:
            current = self._items.get(str(key))
            if current is None or current.owner_id != str(owner_id) or current.state != "in_progress":
                raise ValueError("idempotency reservation ownership mismatch")
            current.state = "completed"
            current.payload = payload
            current.failure_reason = None

    def fail(self, key: str, *, owner_id: str, reason: str) -> None:
        with self._lock:
            current = self._items.get(str(key))
            if current is None or current.owner_id != str(owner_id) or current.state != "in_progress":
                raise ValueError("idempotency reservation ownership mismatch")
            current.state = "failed"
            current.failure_reason = str(reason)

    def put(self, key: str, payload: object) -> None:
        """Compatibility terminal cache for a rejection that occurred before effects."""
        normalized_key = str(key).strip()
        if not normalized_key:
            raise ValueError("idempotency key is required")
        with self._lock:
            current = self._items.get(normalized_key)
            if current is None:
                self._items[normalized_key] = _BusinessIdempotencyRecord(
                    owner_id="compatibility-cache",
                    state="completed",
                    payload=payload,
                )


_PAID_ACTION_TOKENS = (
    "payment",
    "refund",
    "purchase",
    "charge",
    "payout",
    "budget_update",
    "campaign_launch",
    "paid",
)

_EXTERNAL_WRITE_ACTION_TOKENS = (
    "send",
    "publish",
    "update",
    "launch",
    "pause",
    "refund",
    "payment",
    "write",
    "create",
    "delete",
    "dispatch",
    "reconnect",
)


def _action_type(request: BusinessExecutionRequest) -> str:
    return str(request.envelope.metadata.get("action_type") or request.envelope.goal_type or "").strip().lower()


def _requires_explicit_budget(*, request: BusinessExecutionRequest, estimated_cost: float) -> bool:
    action = _action_type(request)
    return estimated_cost > 0 or any(token in action for token in _PAID_ACTION_TOKENS)


def _requires_explicit_blast_limit(*, request: BusinessExecutionRequest, requested: int) -> bool:
    action = _action_type(request)
    return requested > 1 or any(token in action for token in _EXTERNAL_WRITE_ACTION_TOKENS)


def _extract_float_constraint(request: BusinessExecutionRequest, name: str) -> float | None:
    for item in request.envelope.constraints:
        if item.name == name:
            return _finite_float_or_none(item.value)
    return None


def _extract_int_constraint(request: BusinessExecutionRequest, name: str) -> int | None:
    for item in request.envelope.constraints:
        if item.name == name:
            return _strict_int_or_none(item.value)
    return None


def _finite_float_or_none(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _strict_int_or_none(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    try:
        if float(value) != float(parsed):
            return None
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed


def _money_to_minor(value: float) -> int:
    return int(round(float(value) * 100))

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from application.autonomy.autonomy_tiers import ALLOWED_AUTONOMY_TIERS

CANON_AUTONOMY_POLICY = True


_TIER_RANK = {"advisory": 0, "supervised": 1, "bounded_autonomy": 2, "full_autonomy": 3}


def _safe_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_int(value: object, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _normalize_tier(value: object, *, default: str = "supervised") -> str:
    text = str(value or "").strip()
    return text if text in ALLOWED_AUTONOMY_TIERS else default


def _min_tier(left: str, right: str) -> str:
    return left if _TIER_RANK[left] <= _TIER_RANK[right] else right


@dataclass(frozen=True, slots=True)
class AutonomyPolicyInput:
    requested_tier: str = "supervised"
    current_tier: str = "supervised"
    approval_required: bool = False
    operator_required: bool = False
    budget_allowed: bool = True
    spend_limit_allowed: bool = True
    economic_policy_allowed: bool = True
    blast_radius_allowed: bool = True
    revenue_verification_required: bool = False
    revenue_verified: bool = False
    survival_mode: str = "normal"
    economic_operator_required: bool = False
    economic_confidence: float = 1.0
    verification_success_rate: float = 0.0
    recent_verified_runs: int = 0
    recent_failed_runs: int = 0
    has_live_connector_evidence: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_tier": self.requested_tier,
            "current_tier": self.current_tier,
            "approval_required": self.approval_required,
            "operator_required": self.operator_required,
            "budget_allowed": self.budget_allowed,
            "spend_limit_allowed": self.spend_limit_allowed,
            "economic_policy_allowed": self.economic_policy_allowed,
            "blast_radius_allowed": self.blast_radius_allowed,
            "revenue_verification_required": self.revenue_verification_required,
            "revenue_verified": self.revenue_verified,
            "survival_mode": self.survival_mode,
            "economic_operator_required": self.economic_operator_required,
            "economic_confidence": self.economic_confidence,
            "verification_success_rate": self.verification_success_rate,
            "recent_verified_runs": self.recent_verified_runs,
            "recent_failed_runs": self.recent_failed_runs,
            "has_live_connector_evidence": self.has_live_connector_evidence,
        }


@dataclass(frozen=True, slots=True)
class NextTierContext:
    requested_tier: str
    current_tier: str
    ceiling_tier: str
    suggested_tier: str
    escalation_allowed: bool
    notes: tuple[str, ...] = ()
    input_snapshot: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_tier": self.requested_tier,
            "current_tier": self.current_tier,
            "ceiling_tier": self.ceiling_tier,
            "suggested_tier": self.suggested_tier,
            "escalation_allowed": self.escalation_allowed,
            "notes": list(self.notes),
            "input_snapshot": dict(self.input_snapshot),
        }


class AutonomyPolicy:
    def evaluate(self, policy_input: AutonomyPolicyInput) -> NextTierContext:
        requested = _normalize_tier(policy_input.requested_tier)
        current = _normalize_tier(policy_input.current_tier)
        notes: list[str] = []

        if requested == "advisory":
            return NextTierContext(
                requested_tier=requested,
                current_tier=current,
                ceiling_tier="advisory",
                suggested_tier="advisory",
                escalation_allowed=False,
                notes=("Requested tier is advisory",),
                input_snapshot=policy_input.to_dict(),
            )
        if not policy_input.budget_allowed:
            return NextTierContext(requested_tier=requested, current_tier=current, ceiling_tier="advisory", suggested_tier="advisory", escalation_allowed=False, notes=("Operational budget denies escalation",), input_snapshot=policy_input.to_dict())
        if not policy_input.spend_limit_allowed:
            return NextTierContext(requested_tier=requested, current_tier=current, ceiling_tier="advisory", suggested_tier="advisory", escalation_allowed=False, notes=("Spend limit policy denies escalation",), input_snapshot=policy_input.to_dict())
        if not policy_input.economic_policy_allowed:
            return NextTierContext(requested_tier=requested, current_tier=current, ceiling_tier="advisory", suggested_tier="advisory", escalation_allowed=False, notes=("Economic policy veto denies escalation",), input_snapshot=policy_input.to_dict())
        if not policy_input.blast_radius_allowed:
            return NextTierContext(requested_tier=requested, current_tier=current, ceiling_tier="supervised", suggested_tier="supervised", escalation_allowed=False, notes=("Blast radius guard denies escalation",), input_snapshot=policy_input.to_dict())
        if policy_input.approval_required or policy_input.operator_required:
            return NextTierContext(requested_tier=requested, current_tier=current, ceiling_tier="supervised", suggested_tier="supervised", escalation_allowed=False, notes=("Human approval is required",), input_snapshot=policy_input.to_dict())

        ceiling = requested
        if policy_input.survival_mode == "survival":
            ceiling = _min_tier(ceiling, "supervised")
            notes.append("Survival mode forbids autonomy escalation")
        elif policy_input.survival_mode == "defensive":
            ceiling = _min_tier(ceiling, "bounded_autonomy")
            notes.append("Defensive survival mode limits autonomy ceiling")
        if policy_input.economic_operator_required:
            ceiling = _min_tier(ceiling, "supervised")
            notes.append("Economic review requires operator supervision")
        if policy_input.economic_confidence < 0.5:
            ceiling = _min_tier(ceiling, "supervised")
            notes.append("Low economic confidence")
        if not policy_input.has_live_connector_evidence:
            ceiling = _min_tier(ceiling, "supervised")
            notes.append("No live connector evidence")
        if policy_input.recent_failed_runs >= max(2, policy_input.recent_verified_runs + 1):
            ceiling = _min_tier(ceiling, "supervised")
            notes.append("Recent failures dominate")
        if policy_input.verification_success_rate < 0.5 and (policy_input.recent_failed_runs or policy_input.recent_verified_runs):
            ceiling = _min_tier(ceiling, "supervised")
            notes.append("Low verification success rate")
        if policy_input.revenue_verification_required and not policy_input.revenue_verified:
            ceiling = _min_tier(ceiling, "supervised")
            notes.append("Revenue outcome is not externally verified")
        if requested == "full_autonomy" and policy_input.verification_success_rate < 0.9:
            ceiling = _min_tier(ceiling, "bounded_autonomy")
            notes.append("Full autonomy requires higher verification quality")
        if requested in {"bounded_autonomy", "full_autonomy"} and policy_input.recent_verified_runs < 3:
            ceiling = _min_tier(ceiling, "supervised")
            notes.append("Insufficient verified execution history")
        if policy_input.verification_success_rate >= 0.8 and policy_input.recent_verified_runs >= 3 and policy_input.has_live_connector_evidence:
            notes.append("Observed history supports bounded escalation")
        suggested = _min_tier(requested, ceiling)
        return NextTierContext(
            requested_tier=requested,
            current_tier=current,
            ceiling_tier=ceiling,
            suggested_tier=suggested,
            escalation_allowed=_TIER_RANK[suggested] > _TIER_RANK[current],
            notes=tuple(notes),
            input_snapshot=policy_input.to_dict(),
        )


def autonomy_input_from_world_state(
    world_state: Mapping[str, Any] | None,
    *,
    requested_tier: str,
    current_tier: str,
    approval_required: bool,
    budget_allowed: bool,
    blast_radius_allowed: bool,
) -> AutonomyPolicyInput:
    state = _safe_dict(world_state)
    meta = _safe_dict(state.get("meta"))
    closed_loop = _safe_dict(meta.get("execution_closed_loop"))
    history = list(closed_loop.get("execution_history") or [])[:10]
    verified = sum(1 for item in history if _safe_bool(_safe_dict(item).get("verified")))
    failed = sum(1 for item in history if not _safe_bool(_safe_dict(item).get("verified")))
    success_rate = verified / len(history) if history else (1.0 if _safe_bool(_safe_dict(closed_loop.get("last_verification")).get("verified")) else 0.0)
    has_live_connector_evidence = any(_safe_dict(item).get("source_of_truth") in {"router", "observable_evidence"} and _safe_bool(_safe_dict(item).get("verified")) for item in history)

    economic = _safe_dict(meta.get("economic_safety") or state.get("economic_safety"))
    budget_guard = _safe_dict(economic.get("budget_guard"))
    spend_limits = _safe_dict(economic.get("spend_limits") or budget_guard.get("spend_limits"))
    economic_policy = _safe_dict(economic.get("economic_policy") or budget_guard.get("economic_policy"))
    revenue_verification = _safe_dict(economic.get("revenue_verification") or budget_guard.get("revenue_verification"))

    return AutonomyPolicyInput(
        requested_tier=_normalize_tier(requested_tier),
        current_tier=_normalize_tier(current_tier),
        approval_required=approval_required,
        operator_required=_safe_bool(budget_guard.get("operator_required") or economic_policy.get("operator_required")),
        budget_allowed=budget_allowed,
        spend_limit_allowed=not (spend_limits and spend_limits.get("allowed") is False),
        economic_policy_allowed=not (economic_policy and economic_policy.get("allowed") is False),
        blast_radius_allowed=blast_radius_allowed,
        revenue_verification_required=_safe_bool(revenue_verification.get("required") or economic_policy.get("revenue_verification_required")),
        revenue_verified=_safe_bool(revenue_verification.get("verified")),
        survival_mode=str(economic_policy.get("survival_mode") or "normal"),
        economic_operator_required=_safe_bool(economic_policy.get("operator_required")),
        economic_confidence=max(0.0, min(1.0, _safe_float(economic_policy.get("economic_confidence"), default=1.0))),
        verification_success_rate=max(0.0, min(1.0, _safe_float(success_rate, default=0.0))),
        recent_verified_runs=max(0, _safe_int(verified, default=0)),
        recent_failed_runs=max(0, _safe_int(failed, default=0)),
        has_live_connector_evidence=has_live_connector_evidence,
    )


__all__ = [
    "CANON_AUTONOMY_POLICY",
    "AutonomyPolicy",
    "AutonomyPolicyInput",
    "NextTierContext",
    "autonomy_input_from_world_state",
]

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GovernanceInvariantViolation:
    invariant_name: str
    details: dict = field(default_factory=dict)


@dataclass(frozen=True)
class GovernanceInvariantResult:
    allowed: bool
    violations: tuple[GovernanceInvariantViolation, ...] = field(default_factory=tuple)


def evaluate_governance_invariants(
    *,
    action_name: str,
    actor_scope: str,
    rights_allowed: bool,
    forbidden_action: bool,
    maintenance_mode_enabled: bool,
    incident_mode_enabled: bool,
    mandatory_escalation_required: bool,
    escalation_route_present: bool,
) -> GovernanceInvariantResult:
    violations: list[GovernanceInvariantViolation] = []

    if forbidden_action:
        violations.append(
            GovernanceInvariantViolation(
                invariant_name="forbidden_operator_action",
                details={"action_name": action_name},
            )
        )

    if not rights_allowed:
        violations.append(
            GovernanceInvariantViolation(
                invariant_name="decision_rights_violation",
                details={
                    "action_name": action_name,
                    "actor_scope": actor_scope,
                },
            )
        )

    if mandatory_escalation_required and not escalation_route_present:
        violations.append(
            GovernanceInvariantViolation(
                invariant_name="missing_escalation_route",
                details={"action_name": action_name},
            )
        )

    if maintenance_mode_enabled and action_name.startswith("release."):
        violations.append(
            GovernanceInvariantViolation(
                invariant_name="release_blocked_during_maintenance",
                details={"action_name": action_name},
            )
        )

    if incident_mode_enabled and action_name.startswith("policy.version.promote"):
        violations.append(
            GovernanceInvariantViolation(
                invariant_name="policy_promotion_blocked_during_incident",
                details={"action_name": action_name},
            )
        )

    return GovernanceInvariantResult(
        allowed=not violations,
        violations=tuple(violations),
    )

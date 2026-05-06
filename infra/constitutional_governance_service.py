from __future__ import annotations

from dataclasses import dataclass, field

from infra.audit_log_service import AuditLogService
from infra.decision_rights_registry import DecisionRightsRegistry
from infra.escalation_routes import EscalationRoutesRegistry
from infra.forbidden_operator_actions import ForbiddenOperatorActions
from infra.governance_invariants import (
    GovernanceInvariantResult,
    evaluate_governance_invariants,
)
from infra.incident_mode import IncidentMode
from infra.maintenance_mode import MaintenanceMode
from infra.policy_constitution import PolicyConstitution


@dataclass(frozen=True)
class ConstitutionalDecision:
    allowed: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)
    escalation_route: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ConstitutionalGovernanceService:
    rights_registry: DecisionRightsRegistry
    constitution: PolicyConstitution
    forbidden_actions: ForbiddenOperatorActions
    escalation_routes: EscalationRoutesRegistry
    maintenance_mode: MaintenanceMode
    incident_mode: IncidentMode
    audit_log: AuditLogService

    def evaluate(
        self,
        *,
        actor: str,
        actor_scope: str,
        action_name: str,
    ) -> ConstitutionalDecision:
        rights_allowed = self.rights_registry.is_allowed(
            action_name=action_name,
            actor_scope=actor_scope,
        )
        forbidden_action = self.forbidden_actions.contains(action_name)
        mandatory_escalation_required = action_name in set(
            self.constitution.mandatory_escalation_actions
        )
        escalation = self.escalation_routes.get(action_name)
        escalation_route_present = escalation is not None

        invariant_result: GovernanceInvariantResult = evaluate_governance_invariants(
            action_name=action_name,
            actor_scope=actor_scope,
            rights_allowed=rights_allowed,
            forbidden_action=forbidden_action,
            maintenance_mode_enabled=self.maintenance_mode.is_enabled(),
            incident_mode_enabled=self.incident_mode.is_enabled(),
            mandatory_escalation_required=mandatory_escalation_required,
            escalation_route_present=escalation_route_present,
        )

        reasons = tuple(v.invariant_name for v in invariant_result.violations)
        route = escalation.route if escalation is not None else ()

        self.audit_log.record(
            event_name="constitutional_governance_evaluated",
            actor=actor,
            category="constitutional_governance",
            payload={
                "actor_scope": actor_scope,
                "action_name": action_name,
                "allowed": invariant_result.allowed,
                "reasons": list(reasons),
                "escalation_route": list(route),
            },
        )

        return ConstitutionalDecision(
            allowed=invariant_result.allowed,
            reasons=reasons,
            escalation_route=route,
        )

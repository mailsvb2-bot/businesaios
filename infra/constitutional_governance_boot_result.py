from __future__ import annotations

from dataclasses import dataclass

from infra.constitutional_governance_service import ConstitutionalGovernanceService
from infra.decision_rights_registry import DecisionRightsRegistry
from infra.escalation_routes import EscalationRoutesRegistry
from infra.forbidden_operator_actions import ForbiddenOperatorActions
from infra.policy_constitution import PolicyConstitution


@dataclass(frozen=True)
class ConstitutionalGovernanceBootResult:
    rights_registry: DecisionRightsRegistry
    constitution: PolicyConstitution
    forbidden_actions: ForbiddenOperatorActions
    escalation_routes: EscalationRoutesRegistry
    service: ConstitutionalGovernanceService

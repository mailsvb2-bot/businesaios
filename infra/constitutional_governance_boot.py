from __future__ import annotations

from dataclasses import dataclass

from infra.audit_log_service import AuditLogService
from infra.authority_scopes import AuthorityScope
from infra.compliance_boot_result import ComplianceBootResult
from infra.constitutional_governance_boot_result import (
    ConstitutionalGovernanceBootResult,
)
from infra.constitutional_governance_service import ConstitutionalGovernanceService
from infra.decision_rights_registry import DecisionRightsRegistry
from infra.escalation_routes import EscalationRoute, EscalationRoutesRegistry
from infra.forbidden_operator_actions import ForbiddenOperatorActions
from infra.policy_constitution import PolicyConstitution


@dataclass
class ConstitutionalGovernanceBoot:
    compliance: ComplianceBootResult

    def build(self) -> ConstitutionalGovernanceBootResult:
        rights = DecisionRightsRegistry()
        _register_default_rights(rights)

        constitution = PolicyConstitution(
            name="system_constitution_v1",
            immutable_rules=(
                "no_hidden_decision_engine",
                "no_operator_bypass_of_decision_core",
                "no_policy_promotion_without_traceability",
            ),
            mandatory_escalation_actions=(
                "release.promote.prod",
                "policy.version.promote",
                "kill_switch.reset.global",
            ),
            protected_actions=(
                "release.promote.prod",
                "rollback.execute.prod",
            ),
        )

        forbidden = ForbiddenOperatorActions(
            actions=(
                "decision_core.override",
                "raw_runtime_rewire",
                "policy.trace.delete",
            )
        )

        escalations = EscalationRoutesRegistry()
        escalations.register(
            EscalationRoute(
                action_name="release.promote.prod",
                route=(AuthorityScope.OPS, AuthorityScope.RISK, AuthorityScope.EXECUTIVE),
            )
        )
        escalations.register(
            EscalationRoute(
                action_name="policy.version.promote",
                route=(AuthorityScope.PLATFORM, AuthorityScope.RISK, AuthorityScope.EXECUTIVE),
            )
        )
        escalations.register(
            EscalationRoute(
                action_name="kill_switch.reset.global",
                route=(AuthorityScope.OPS, AuthorityScope.SECURITY),
            )
        )

        service = ConstitutionalGovernanceService(
            rights_registry=rights,
            constitution=constitution,
            forbidden_actions=forbidden,
            escalation_routes=escalations,
            maintenance_mode=self.compliance.operator_actions.maintenance_mode,
            incident_mode=self.compliance.incident_mode,
            audit_log=self.compliance.audit_log,
        )

        self.compliance.audit_log.record(
            event_name="constitutional_governance_boot_completed",
            actor="system",
            category="constitutional_governance_boot",
            payload={},
        )

        return ConstitutionalGovernanceBootResult(
            rights_registry=rights,
            constitution=constitution,
            forbidden_actions=forbidden,
            escalation_routes=escalations,
            service=service,
        )


def _register_default_rights(rights: DecisionRightsRegistry) -> None:
    rights.register("release.promote.stage", (AuthorityScope.OPS, AuthorityScope.PLATFORM))
    rights.register("release.promote.prod", (AuthorityScope.OPS,))
    rights.register("rollback.execute.prod", (AuthorityScope.OPS, AuthorityScope.RISK))
    rights.register("kill_switch.trip.global", (AuthorityScope.OPS, AuthorityScope.SECURITY))
    rights.register("kill_switch.reset.global", (AuthorityScope.OPS,))
    rights.register("policy.version.promote", (AuthorityScope.PLATFORM,))
    rights.register("feature_flag.enable", (AuthorityScope.PLATFORM, AuthorityScope.PRODUCT))
    rights.register("feature_flag.disable", (AuthorityScope.PLATFORM, AuthorityScope.PRODUCT))

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional

from compliance.action_compliance_policy import ActionComplianceInput, ActionCompliancePolicy, ActionComplianceVerdict
from compliance.approval_compliance_policy import (
    ApprovalComplianceInput,
    ApprovalCompliancePolicy,
    ApprovalComplianceVerdict,
)
from compliance.connector_compliance_matrix import (
    ConnectorComplianceDecision,
    ConnectorComplianceMatrix,
)
from compliance.data_classification import DataAsset, DataClassificationResult, KeywordDataClassifier
from compliance.regional_data_policy import RegionalDataPolicy, RegionalPolicyDecision


@dataclass(frozen=True)
class ComplianceBundleInput:
    data_asset: DataAsset
    action: ActionComplianceInput
    estimated_budget_impact: float = 0.0
    external_data_transfer: bool = False
    cross_region_transfer: bool = False
    target_region: Optional[str] = None
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ComplianceBundleVerdict:
    allowed: bool
    classification: DataClassificationResult
    regional: RegionalPolicyDecision
    connector: ConnectorComplianceDecision
    action: ActionComplianceVerdict
    approval: ApprovalComplianceVerdict
    blocking_reasons: tuple[str, ...]
    required_controls: tuple[str, ...]


class ComplianceBundle:
    """One orchestrated compliance pass, not a second DecisionCore."""

    def __init__(
        self,
        *,
        classifier: Optional[KeywordDataClassifier] = None,
        regional_policy: Optional[RegionalDataPolicy] = None,
        connector_matrix: Optional[ConnectorComplianceMatrix] = None,
        action_policy: Optional[ActionCompliancePolicy] = None,
        approval_policy: Optional[ApprovalCompliancePolicy] = None,
    ) -> None:
        self._classifier = classifier or KeywordDataClassifier()
        self._regional_policy = regional_policy or RegionalDataPolicy()
        self._connector_matrix = connector_matrix or ConnectorComplianceMatrix()
        self._action_policy = action_policy or ActionCompliancePolicy()
        self._approval_policy = approval_policy or ApprovalCompliancePolicy(action_policy=self._action_policy)

    def evaluate(self, payload: ComplianceBundleInput) -> ComplianceBundleVerdict:
        classification = self._classifier.classify(payload.data_asset)
        regional = self._regional_policy.evaluate(
            source_region=payload.data_asset.region_hint,
            target_region=payload.target_region,
            contains_pii=classification.pii_present,
            regulated=bool(classification.regulated_markers),
        )
        connector_name = (payload.action.connector_name or '').strip()
        connector = self._connector_matrix.evaluate(
            connector_name=connector_name,
            target_region=payload.target_region,
            contains_pii=classification.pii_present,
            contains_secrets=classification.secret_present,
            cross_region_transfer=payload.cross_region_transfer,
        )
        enriched_action = ActionComplianceInput(
            action_type=payload.action.action_type,
            action_scope=payload.action.action_scope,
            actor_type=payload.action.actor_type,
            tenant_id=payload.action.tenant_id,
            region=payload.action.region,
            connector_name=payload.action.connector_name,
            contains_pii=classification.pii_present or payload.action.contains_pii,
            contains_secrets=classification.secret_present or payload.action.contains_secrets,
            evidence_required=payload.action.evidence_required,
            outbound_effect=payload.action.outbound_effect,
            destructive=payload.action.destructive,
            metadata=payload.action.metadata,
        )
        action = self._action_policy.evaluate(enriched_action)
        approval = self._approval_policy.evaluate(
            ApprovalComplianceInput(
                action=enriched_action,
                estimated_budget_impact=payload.estimated_budget_impact,
                external_data_transfer=payload.external_data_transfer,
                cross_region_transfer=payload.cross_region_transfer,
            )
        )

        blocking_reasons: list[str] = []
        required_controls: set[str] = set()
        if not regional.allowed:
            blocking_reasons.append(f'regional:{regional.reason}')
        if not connector.allowed:
            blocking_reasons.append(f'connector:{connector.reason}')
        if not action.allowed:
            blocking_reasons.append(f'action:{action.reason}')
        if not approval.allowed:
            blocking_reasons.append(f'approval:{approval.reason}')

        required_controls.update(control.value for control in regional.required_controls)
        required_controls.update(control.value for control in connector.required_controls)
        required_controls.update(control.value for control in action.required_controls)

        return ComplianceBundleVerdict(
            allowed=not blocking_reasons,
            classification=classification,
            regional=regional,
            connector=connector,
            action=action,
            approval=approval,
            blocking_reasons=tuple(blocking_reasons),
            required_controls=tuple(sorted(required_controls)),
        )

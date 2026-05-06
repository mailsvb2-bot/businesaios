from __future__ import annotations

"""Thin boundary adapter for integrating the security engine into surfaces."""

from dataclasses import dataclass, field
from typing import Any, Mapping

from compliance.data_classification import DataClassificationResult, KeywordDataClassifier
from governance.rbac_contract import ActorContext
from observability.security_audit_log import SecurityAuditLog
from security.access_policy import SecurityAction, SecurityResource
from security.security_policy_engine import SecurityPolicyEngine


CANON_SECURITY_INTEGRATION_ADAPTER = True


@dataclass
class SecurityIntegrationAdapter:
    engine: SecurityPolicyEngine
    audit_log: SecurityAuditLog
    classifier: KeywordDataClassifier = field(default_factory=KeywordDataClassifier)

    def evaluate_surface(
        self,
        *,
        actor: ActorContext,
        resource_type: str,
        resource_id: str,
        action: SecurityAction,
        auth_payload: Mapping[str, Any],
        session_payload: Mapping[str, Any],
        compliance_evidence: Mapping[str, object],
        fraud_signals: Mapping[str, float | int | bool],
        transport_encrypted: bool,
        classification_input: Mapping[str, Any],
        audit_payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        classification = self._classify(classification_input)
        resource = SecurityResource(
            resource_type=resource_type,
            resource_id=resource_id,
            tenant_id=actor.tenant_id,
            classification=classification,
            encryption_required=classification.sensitivity.value in {'high', 'critical'},
            attributes={'surface': resource_type},
        )
        verdict = self.engine.evaluate(
            actor=actor,
            resource=resource,
            action=action,
            auth_payload=auth_payload,
            session_payload=session_payload,
            transport_encrypted=transport_encrypted,
            compliance_evidence=compliance_evidence,
            fraud_signals=fraud_signals,
        )
        self.audit_log.append(
            tenant_id=actor.tenant_id,
            event_type='security.surface_evaluation',
            severity='warning' if not verdict.allowed else 'info',
            actor_id=actor.actor_id,
            subject_id=resource.resource_id,
            payload={
                'resource_type': resource_type,
                'action': action.value,
                'allowed': verdict.allowed,
                'reason': verdict.reason,
                'operator_required': verdict.operator_required,
                'classification': classification.category.value,
                'sensitivity': classification.sensitivity.value,
                **dict(audit_payload or {}),
            },
        )
        return {
            'allowed': verdict.allowed,
            'reason': verdict.reason,
            'operator_required': verdict.operator_required,
            'evidence': dict(verdict.evidence),
            'classification': {
                'category': classification.category.value,
                'sensitivity': classification.sensitivity.value,
                'confidence': classification.classification_confidence,
            },
            'token': {
                'allowed': verdict.token.allowed,
                'reason': verdict.token.reason,
                'requires_reissue': verdict.token.requires_reissue,
                'labels': dict(verdict.token.labels),
            },
            'session': {
                'allowed': verdict.session.allowed,
                'reason': verdict.session.reason,
                'invalidate_session': verdict.session.invalidate_session,
                'rotate_session': verdict.session.rotate_session,
                'labels': dict(verdict.session.labels),
            },
            'fraud': {
                'allowed': verdict.fraud.allowed,
                'risk_score': verdict.fraud.risk_score,
                'reason': verdict.fraud.reason,
                'triggered_signals': list(verdict.fraud.triggered_signals),
            },
            'compliance': {
                'compliant': verdict.compliance.compliant,
                'score': verdict.compliance.score,
                'failed_controls': list(verdict.compliance.failed_controls),
                'critical_failure_ids': list(verdict.compliance.critical_failure_ids),
            },
        }

    def _classify(self, payload: Mapping[str, Any]) -> DataClassificationResult:
        from compliance.data_classification import DataAsset

        data = dict(payload or {})
        asset = DataAsset(
            asset_id=str(data.get('asset_id') or 'surface-asset'),
            name=str(data.get('name') or 'surface-asset'),
            content_type=str(data.get('content_type') or 'application/octet-stream'),
            tags=tuple(str(item) for item in (data.get('tags') or ())),
            metadata=dict(data.get('metadata') or {}),
            source_system=str(data.get('source_system') or '') or None,
            region_hint=str(data.get('region_hint') or '') or None,
        )
        return self.classifier.classify(asset)


__all__ = [
    'CANON_SECURITY_INTEGRATION_ADAPTER',
    'SecurityIntegrationAdapter',
]

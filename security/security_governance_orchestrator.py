from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from security.security_approval_gate import SecurityApprovalGate
from security.signed_operator_approval import SignedOperatorApprovalStore
from security.security_incident_registry import SQLiteSecurityIncidentRegistry
from security.token_revocation_store import SQLiteTokenRevocationStore
from security.security_quarantine_registry import SQLiteSecurityQuarantineRegistry
from security.security_audit_chain import SQLiteSecurityAuditChain
from security.security_operator_workflow_store import SQLiteSecurityOperatorWorkflowStore
from security.security_incident_recovery_orchestrator import SecurityIncidentRecoveryOrchestrator, SecurityIncidentRecoveryReport


CANON_SECURITY_GOVERNANCE_ORCHESTRATOR = True


@dataclass(frozen=True)
class SecurityGovernanceReport:
    success: bool
    phase: str
    reason: str
    details: dict[str, Any]


class SecurityGovernanceOrchestrator:
    """Canonical governance owner for high-risk security operations.

    It does not invent new crypto/secret logic. It only coordinates approval,
    incident, quarantine, revoke, and audit-chain steps around the existing security plane.
    """

    def __init__(
        self,
        *,
        approval_gate: SecurityApprovalGate,
        approval_store: SignedOperatorApprovalStore,
        incident_registry: SQLiteSecurityIncidentRegistry,
        revocation_store: SQLiteTokenRevocationStore,
        quarantine_registry: SQLiteSecurityQuarantineRegistry,
        audit_chain: SQLiteSecurityAuditChain,
        workflow_store: SQLiteSecurityOperatorWorkflowStore | None = None,
        recovery_orchestrator: SecurityIncidentRecoveryOrchestrator | None = None,
        approval_replay_guard=None,
    ) -> None:
        self._approval_gate = approval_gate
        self._approval_store = approval_store
        self._incident_registry = incident_registry
        self._revocation_store = revocation_store
        self._quarantine_registry = quarantine_registry
        self._audit_chain = audit_chain
        self._workflow_store = workflow_store
        self._recovery = recovery_orchestrator
        self._approval_replay_guard = approval_replay_guard

    def execute_high_risk_operation(
        self,
        *,
        operation_kind: str,
        actor: str,
        approval_id: str | None,
        payload: Mapping[str, Any],
    ) -> SecurityGovernanceReport:
        verdict = self._approval_gate.evaluate(operation_kind=operation_kind)
        if self._workflow_store is not None:
            self._workflow_store.append_step(
                workflow_id=str(approval_id or 'inline-' + operation_kind),
                operation_kind=operation_kind,
                actor=actor,
                step_kind='requested',
                payload=dict(payload),
            )
        if verdict.requires_signed_approval:
            if not approval_id:
                return SecurityGovernanceReport(False, 'approval', 'signed approval required', {})
            verified = self._approval_store.verify(approval_id=approval_id)
            if not verified.get('ok', False):
                return SecurityGovernanceReport(False, 'approval', 'signed approval verification failed', {'approval_id': approval_id})
            if str(verified.get('operation_kind')) != str(operation_kind):
                return SecurityGovernanceReport(False, 'approval', 'approval operation mismatch', {'approval_id': approval_id})
            if str(verified.get('actor')) != str(actor):
                return SecurityGovernanceReport(False, 'approval', 'approval actor mismatch', {'approval_id': approval_id})
            if self._approval_replay_guard is not None:
                consumed = self._approval_replay_guard.consume(
                    approval_id=str(approval_id),
                    operation_kind=str(operation_kind),
                    actor=str(actor),
                )
                if not consumed:
                    return SecurityGovernanceReport(False, 'approval', 'approval replay detected', {'approval_id': approval_id})

        self._audit_chain.append(
            event_kind='security.governance.operation',
            payload={'operation_kind': operation_kind, 'actor': actor, 'payload': dict(payload)},
        )
        if self._workflow_store is not None:
            self._workflow_store.append_step(
                workflow_id=str(approval_id or 'inline-' + operation_kind),
                operation_kind=operation_kind,
                actor=actor,
                step_kind='completed',
                payload={'requires_signed_approval': verdict.requires_signed_approval},
            )
        return SecurityGovernanceReport(True, 'completed', verdict.reason, {'requires_signed_approval': verdict.requires_signed_approval})

    def quarantine_compromised_token(
        self,
        *,
        token_fingerprint: str,
        actor: str,
        reason: str,
    ) -> SecurityGovernanceReport:
        incident_id = self._incident_registry.open_incident(
            incident_kind='compromised-token',
            payload={'token_fingerprint': token_fingerprint, 'actor': actor, 'reason': reason},
        )
        self._revocation_store.revoke(token_fingerprint=token_fingerprint, reason=reason)
        self._quarantine_registry.quarantine(
            entity_kind='token',
            entity_id=token_fingerprint,
            reason=reason,
            payload={'actor': actor, 'incident_id': incident_id},
        )
        self._audit_chain.append(
            event_kind='security.governance.quarantine',
            payload={'entity_kind': 'token', 'entity_id': token_fingerprint, 'incident_id': incident_id, 'actor': actor},
        )
        return SecurityGovernanceReport(
            True,
            'completed',
            'token revoked and quarantined',
            {'incident_id': incident_id, 'token_fingerprint': token_fingerprint},
        )

    def quarantine_compromised_secret(
        self,
        *,
        secret_id: str,
        actor: str,
        reason: str,
    ) -> SecurityGovernanceReport:
        incident_id = self._incident_registry.open_incident(
            incident_kind='compromised-secret',
            payload={'secret_id': secret_id, 'actor': actor, 'reason': reason},
        )
        self._quarantine_registry.quarantine(
            entity_kind='secret',
            entity_id=secret_id,
            reason=reason,
            payload={'actor': actor, 'incident_id': incident_id},
        )
        self._audit_chain.append(
            event_kind='security.governance.quarantine',
            payload={'entity_kind': 'secret', 'entity_id': secret_id, 'incident_id': incident_id, 'actor': actor},
        )
        return SecurityGovernanceReport(
            True,
            'completed',
            'secret quarantined',
            {'incident_id': incident_id, 'secret_id': secret_id},
        )

    def recover_quarantined_entity(
        self,
        *,
        incident_id: int,
        entity_kind: str,
        entity_id: str,
        actor: str,
        resolution_payload: Mapping[str, Any] | None = None,
    ) -> SecurityGovernanceReport:
        if self._recovery is None:
            return SecurityGovernanceReport(False, 'recovery', 'recovery orchestrator not configured', {})
        result = self._recovery.recover_quarantined_entity(
            incident_id=incident_id,
            entity_kind=entity_kind,
            entity_id=entity_id,
            actor=actor,
            resolution_payload=resolution_payload,
            release_quarantine=True,
        )
        return SecurityGovernanceReport(result.success, 'completed' if result.success else 'recovery', result.reason, result.details)


__all__ = [
    'CANON_SECURITY_GOVERNANCE_ORCHESTRATOR',
    'SecurityGovernanceOrchestrator',
    'SecurityGovernanceReport',
]

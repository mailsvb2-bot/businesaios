from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from security.security_incident_registry import SQLiteSecurityIncidentRegistry
from security.security_quarantine_registry import SQLiteSecurityQuarantineRegistry
from security.security_audit_chain import SQLiteSecurityAuditChain
from security.security_incident_drill_history import SQLiteSecurityIncidentDrillHistory


CANON_SECURITY_INCIDENT_RECOVERY_ORCHESTRATOR = True


@dataclass(frozen=True)
class SecurityIncidentRecoveryReport:
    success: bool
    reason: str
    details: dict[str, Any]


class SecurityIncidentRecoveryOrchestrator:
    """Canonical owner of controlled recovery from security incidents.

    Does not silently un-revoke secrets/tokens. It resolves incident state,
    optionally releases quarantine, and records an audit/drill trail.
    """

    def __init__(
        self,
        *,
        incident_registry: SQLiteSecurityIncidentRegistry,
        quarantine_registry: SQLiteSecurityQuarantineRegistry,
        audit_chain: SQLiteSecurityAuditChain,
        drill_history: SQLiteSecurityIncidentDrillHistory,
    ) -> None:
        self._incidents = incident_registry
        self._quarantine = quarantine_registry
        self._audit = audit_chain
        self._drills = drill_history

    def recover_quarantined_entity(
        self,
        *,
        incident_id: int,
        entity_kind: str,
        entity_id: str,
        actor: str,
        resolution_payload: Mapping[str, Any] | None = None,
        release_quarantine: bool = True,
    ) -> SecurityIncidentRecoveryReport:
        released = False
        if release_quarantine:
            released = self._quarantine.release(entity_kind=entity_kind, entity_id=entity_id)

        resolved = self._incidents.resolve(
            incident_id=int(incident_id),
            resolution_payload={
                'actor': str(actor),
                'entity_kind': str(entity_kind),
                'entity_id': str(entity_id),
                **dict(resolution_payload or {}),
            },
        )

        self._audit.append(
            event_kind='security.incident.recovered',
            payload={
                'incident_id': int(incident_id),
                'entity_kind': str(entity_kind),
                'entity_id': str(entity_id),
                'actor': str(actor),
                'released_quarantine': bool(released),
                'incident_resolved': bool(resolved),
            },
        )
        self._drills.append(
            drill_kind='security.incident.recovery',
            ok=bool(resolved),
            payload={
                'incident_id': int(incident_id),
                'entity_kind': str(entity_kind),
                'entity_id': str(entity_id),
                'actor': str(actor),
                'released_quarantine': bool(released),
            },
        )

        return SecurityIncidentRecoveryReport(
            success=bool(resolved),
            reason='incident recovered' if resolved else 'incident recovery failed',
            details={
                'incident_id': int(incident_id),
                'released_quarantine': bool(released),
                'incident_resolved': bool(resolved),
            },
        )

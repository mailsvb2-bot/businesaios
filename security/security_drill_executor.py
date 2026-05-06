from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from security.security_governance_orchestrator import SecurityGovernanceOrchestrator


CANON_SECURITY_DRILL_EXECUTOR = True


@dataclass(frozen=True)
class SecurityDrillReport:
    success: bool
    phase: str
    reason: str
    details: dict[str, Any]


class SecurityDrillExecutor:
    """Canonical owner for reproducible security incident drills.

    It exercises the existing security governance plane end-to-end instead of
    inventing a shadow simulation system.
    """

    def __init__(self, *, governance: SecurityGovernanceOrchestrator) -> None:
        self._governance = governance

    def run_token_quarantine_recovery_drill(
        self,
        *,
        actor: str,
        token_fingerprint: str,
        reason: str = 'drill',
    ) -> SecurityDrillReport:
        quarantine = self._governance.quarantine_compromised_token(
            token_fingerprint=token_fingerprint,
            actor=actor,
            reason=reason,
        )
        if not quarantine.success:
            return SecurityDrillReport(False, quarantine.phase, quarantine.reason, quarantine.details)

        incident_id = int(quarantine.details['incident_id'])
        recovery = self._governance.recover_quarantined_entity(
            incident_id=incident_id,
            entity_kind='token',
            entity_id=token_fingerprint,
            actor=actor,
            resolution_payload={'drill': True},
        )
        return SecurityDrillReport(recovery.success, recovery.phase, recovery.reason, recovery.details)

    def run_secret_quarantine_recovery_drill(
        self,
        *,
        actor: str,
        secret_id: str,
        reason: str = 'drill',
    ) -> SecurityDrillReport:
        quarantine = self._governance.quarantine_compromised_secret(
            secret_id=secret_id,
            actor=actor,
            reason=reason,
        )
        if not quarantine.success:
            return SecurityDrillReport(False, quarantine.phase, quarantine.reason, quarantine.details)

        incident_id = int(quarantine.details['incident_id'])
        recovery = self._governance.recover_quarantined_entity(
            incident_id=incident_id,
            entity_kind='secret',
            entity_id=secret_id,
            actor=actor,
            resolution_payload={'drill': True},
        )
        return SecurityDrillReport(recovery.success, recovery.phase, recovery.reason, recovery.details)


__all__ = [
    'CANON_SECURITY_DRILL_EXECUTOR',
    'SecurityDrillExecutor',
    'SecurityDrillReport',
]

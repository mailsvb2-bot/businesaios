from __future__ import annotations

from dataclasses import dataclass

from security.governance_journal import GovernanceJournalEvent, SQLiteGovernanceJournal
from security.security_incident_registry import SQLiteSecurityIncidentRegistry

CANON_SECURITY_CHAOS_MODE = True

@dataclass(frozen=True)
class SecurityChaosReport:
    simulated_event: str
    incident_id: int


class SecurityChaosMode:
    def __init__(self, *, incident_registry: SQLiteSecurityIncidentRegistry, governance_journal: SQLiteGovernanceJournal) -> None:
        self._incidents = incident_registry
        self._journal = governance_journal

    def simulate(self, *, event_kind: str, target_id: str) -> SecurityChaosReport:
        incident_id = self._incidents.open_incident(incident_kind=f'chaos:{event_kind}', payload={'target_id': str(target_id)})
        self._journal.append(GovernanceJournalEvent(event_kind='chaos.simulated', entity_kind='security-chaos', entity_id=str(target_id), payload={'event_kind': str(event_kind)}, related_incident_id=incident_id))
        return SecurityChaosReport(simulated_event=str(event_kind), incident_id=incident_id)

__all__ = ['CANON_SECURITY_CHAOS_MODE', 'SecurityChaosMode', 'SecurityChaosReport']

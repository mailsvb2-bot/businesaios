from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from runtime.platform.security_sqlite_stores import SQLiteGovernanceJournalStore

CANON_GOVERNANCE_JOURNAL = True


@dataclass(frozen=True)
class GovernanceJournalEvent:
    event_kind: str
    entity_kind: str
    entity_id: str
    payload: Mapping[str, Any]
    related_incident_id: int | None = None
    related_approval_id: str | None = None
    related_drill_kind: str | None = None


class SQLiteGovernanceJournal:
    """Security-facing governance journal facade.

    SQLite ownership lives in runtime.platform.security_sqlite_stores.
    """

    def __init__(self, db_path: str) -> None:
        self._store = SQLiteGovernanceJournalStore(db_path)

    @staticmethod
    def _tenant_match(*, event_payload: Mapping[str, Any], entity_id: str, tenant_id: str) -> bool:
        tenant_norm = str(tenant_id or '').strip()
        if not tenant_norm:
            raise ValueError('tenant_id is required')
        entity_norm = str(entity_id or '')
        payload_tenant = str(dict(event_payload or {}).get('tenant_id', '')).strip()
        return entity_norm.startswith(f'tenant:{tenant_norm}:') or payload_tenant == tenant_norm

    def append(self, event: GovernanceJournalEvent) -> dict[str, Any]:
        return self._store.append(
            event_kind=event.event_kind,
            entity_kind=event.entity_kind,
            entity_id=event.entity_id,
            payload=event.payload,
            related_incident_id=event.related_incident_id,
            related_approval_id=event.related_approval_id,
            related_drill_kind=event.related_drill_kind,
        )

    def latest(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return self._store.latest(limit=limit)

    def latest_for_tenant(self, *, tenant_id: str, limit: int = 100) -> list[dict[str, Any]]:
        events = self.latest(limit=max(int(limit) * 4, 100))
        filtered = [
            item for item in events
            if self._tenant_match(event_payload=dict(item.get('payload') or {}), entity_id=str(item.get('entity_id', '')), tenant_id=tenant_id)
        ]
        return filtered[:max(int(limit), 1)]

    def latest_entity_timeline(self, *, entity_kind: str, entity_id: str, limit: int = 100) -> list[dict[str, Any]]:
        return self._store.latest_entity_timeline(entity_kind=entity_kind, entity_id=entity_id, limit=limit)

    def latest_entity_timeline_for_tenant(self, *, tenant_id: str, entity_kind: str, entity_id: str, limit: int = 100) -> list[dict[str, Any]]:
        timeline = self.latest_entity_timeline(entity_kind=entity_kind, entity_id=entity_id, limit=limit)
        if not timeline:
            return []
        if not self._tenant_match(event_payload=dict(timeline[0].get('payload') or {}), entity_id=entity_id, tenant_id=tenant_id):
            raise PermissionError('cross-tenant governance timeline access denied')
        return timeline


__all__ = ['CANON_GOVERNANCE_JOURNAL', 'GovernanceJournalEvent', 'SQLiteGovernanceJournal']

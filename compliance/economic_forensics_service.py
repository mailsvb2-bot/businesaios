from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping, Sequence

from compliance.economic_forensics_contract import EconomicForensicsEvent, EconomicForensicsExportBundle
from compliance.economic_forensics_store import EconomicForensicsStore, NoOpEconomicForensicsStore

CANON_ECONOMIC_FORENSICS_SERVICE = True


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return str(value or '').strip()


class EconomicForensicsService:
    """
    Regulated-grade evidence logger for economic bundle lifecycle.

    Important:
    - Does not issue decisions.
    - Does not modify economic policy outputs.
    - Only records audit-grade forensic evidence around existing economic flows.
    """

    def __init__(self, *, store: EconomicForensicsStore | None = None) -> None:
        self._store = store or NoOpEconomicForensicsStore()

    def record_event(
        self,
        *,
        event_type: str,
        severity: str,
        artifact_id: str = '',
        artifact_digest: str = '',
        scope: Mapping[str, Any] | None = None,
        schema_version: str = '',
        payload: Mapping[str, Any] | None = None,
        tags: Sequence[str] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> EconomicForensicsEvent:
        scope_payload = _safe_dict(scope)
        event = EconomicForensicsEvent(
            event_id=sha256(_stable_json({
                'event_type': event_type,
                'severity': severity,
                'artifact_id': artifact_id,
                'artifact_digest': artifact_digest,
                'scope': scope_payload,
                'payload': _safe_dict(payload),
                'generated_at': _utc_now(),
            }).encode('utf-8')).hexdigest(),
            event_type=_text(event_type),
            severity=_text(severity) or 'info',
            artifact_id=_text(artifact_id),
            artifact_digest=_text(artifact_digest),
            tenant_id=_text(scope_payload.get('tenant_id')),
            business_id=_text(scope_payload.get('business_id')),
            schema_version=_text(schema_version),
            payload=_safe_dict(payload),
            tags=tuple(str(x) for x in tags if _text(x)),
            metadata={'owner': 'compliance.economic_forensics_service', **_safe_dict(metadata)},
        )
        return self._store.append(event)

    def export_bundle(self, *, bundle_id: str, events: Sequence[EconomicForensicsEvent] | None = None) -> EconomicForensicsExportBundle:
        rows = [e.to_dict() if hasattr(e, 'to_dict') else asdict(e) for e in (events or self._store.list_rows())]
        generated_at = _utc_now()
        integrity_sha256 = sha256(_stable_json({'bundle_id': bundle_id, 'generated_at': generated_at, 'events': rows}).encode('utf-8')).hexdigest()
        return EconomicForensicsExportBundle(
            bundle_id=_text(bundle_id) or 'economic-forensics',
            generated_at=generated_at,
            event_count=len(rows),
            integrity_sha256=integrity_sha256,
            events=tuple(rows),
            metadata={'owner': 'compliance.economic_forensics_service'},
        )

    def write_bundle(self, *, bundle_id: str, path: str | Path, events: Sequence[EconomicForensicsEvent] | None = None) -> str:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        bundle = self.export_bundle(bundle_id=bundle_id, events=events)
        target.write_text(json.dumps(bundle.to_dict(), ensure_ascii=False, sort_keys=True, indent=2), encoding='utf-8')
        return str(target)


__all__ = [
    'CANON_ECONOMIC_FORENSICS_SERVICE',
    'EconomicForensicsService',
]

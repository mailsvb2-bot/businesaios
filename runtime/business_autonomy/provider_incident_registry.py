
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from collections.abc import Mapping
from uuid import uuid4

from application.business_autonomy.persistence import business_autonomy_runtime_dir

CANON_PROVIDER_INCIDENT_REGISTRY = True


def _incident_path() -> Path:
    path = business_autonomy_runtime_dir() / 'provider_runtime_incidents.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class FileProviderIncidentRegistry:
    path: Path = field(default_factory=_incident_path)

    def append(self, row: Mapping[str, Any]) -> dict[str, Any]:
        normalized = {
            'incident_id': str(row.get('incident_id') or f"incident-{uuid4().hex}"),
            'tenant_id': str(row.get('tenant_id') or '').strip(),
            'business_id': str(row.get('business_id') or '').strip(),
            'provider_key': str(row.get('provider_key') or '').strip(),
            'kind': str(row.get('kind') or 'runtime').strip() or 'runtime',
            'status': str(row.get('status') or 'unknown').strip() or 'unknown',
            'severity': str(row.get('severity') or 'major').strip() or 'major',
            'category': str(row.get('category') or '').strip(),
            'message': str(row.get('message') or '').strip(),
            'retryable': bool(row.get('retryable', False)),
            'recorded_at_utc': str(row.get('recorded_at_utc') or _now()),
            'metadata': dict(row.get('metadata') or {}),
        }
        with self.path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(normalized, ensure_ascii=False, sort_keys=True) + '\n')
        return normalized

    def list_for_provider(self, *, tenant_id: str, business_id: str, provider_key: str, limit: int = 50) -> tuple[dict[str, Any], ...]:
        rows: list[dict[str, Any]] = []
        if not self.path.exists():
            return ()
        with self.path.open('r', encoding='utf-8') as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = dict(json.loads(line))
                except Exception:
                    continue
                if str(row.get('tenant_id')) != str(tenant_id):
                    continue
                if str(row.get('business_id')) != str(business_id):
                    continue
                if str(row.get('provider_key')) != str(provider_key):
                    continue
                rows.append(row)
        return tuple(rows[-max(int(limit), 0):][::-1]) if limit else tuple(rows[::-1])


__all__ = ['CANON_PROVIDER_INCIDENT_REGISTRY', 'FileProviderIncidentRegistry']

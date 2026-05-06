from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any

from contracts.platforms.market_intelligence_advanced_contract import ProviderCursor

CANON_MARKET_INTELLIGENCE_CURSOR_STORE = True


def _safe_key(*parts: object) -> str:
    raw = '__'.join(str(part or '').strip() or 'unknown' for part in parts)
    return ''.join(ch if ch.isalnum() or ch in {'-', '_'} else '_' for ch in raw)


@dataclass
class PersistentMarketIntelligenceCursorStore:
    root_dir: Path = Path('.runtime_data/market_intelligence/cursors')

    def _path(self, *, tenant_id: str, provider: str, source_family: str, scope_key: str) -> Path:
        return self.root_dir / _safe_key(tenant_id) / f'{_safe_key(provider, source_family, scope_key)}.json'

    def load(self, *, tenant_id: str, provider: str, source_family: str, scope_key: str) -> ProviderCursor:
        path = self._path(tenant_id=tenant_id, provider=provider, source_family=source_family, scope_key=scope_key)
        if not path.exists():
            return ProviderCursor(tenant_id=tenant_id, provider=provider, source_family=source_family, scope_key=scope_key)
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            return ProviderCursor(tenant_id=tenant_id, provider=provider, source_family=source_family, scope_key=scope_key)
        if not isinstance(payload, dict):
            return ProviderCursor(tenant_id=tenant_id, provider=provider, source_family=source_family, scope_key=scope_key)
        safe_payload = {
            'tenant_id': payload.get('tenant_id', tenant_id),
            'provider': payload.get('provider', provider),
            'source_family': payload.get('source_family', source_family),
            'scope_key': payload.get('scope_key', scope_key),
            'cursor': payload.get('cursor'),
            'last_seen_at': payload.get('last_seen_at'),
            'checksum': payload.get('checksum'),
            'updated_at': payload.get('updated_at'),
            'metadata': payload.get('metadata') or {},
        }
        try:
            return ProviderCursor(**safe_payload)
        except Exception:
            return ProviderCursor(tenant_id=tenant_id, provider=provider, source_family=source_family, scope_key=scope_key)

    def save(self, cursor: ProviderCursor) -> ProviderCursor:
        path = self._path(
            tenant_id=cursor.tenant_id,
            provider=cursor.provider,
            source_family=cursor.source_family,
            scope_key=cursor.scope_key,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + '.tmp')
        tmp_path.write_text(json.dumps(cursor.as_dict(), ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(tmp_path, path)
        return cursor

    def snapshot(self) -> tuple[dict[str, Any], ...]:
        rows: list[dict[str, Any]] = []
        if not self.root_dir.exists():
            return ()
        for path in sorted(self.root_dir.rglob('*.json')):
            try:
                payload = json.loads(path.read_text(encoding='utf-8'))
            except Exception:
                continue
            if isinstance(payload, dict):
                rows.append(dict(payload))
        return tuple(rows)


__all__ = ['CANON_MARKET_INTELLIGENCE_CURSOR_STORE', 'PersistentMarketIntelligenceCursorStore']

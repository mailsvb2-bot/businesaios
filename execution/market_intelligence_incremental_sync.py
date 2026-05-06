from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
from typing import Any, Mapping

from contracts.platforms.market_intelligence_advanced_contract import ProviderCursor
from execution.market_intelligence_cursor_store import PersistentMarketIntelligenceCursorStore


CANON_MARKET_INTELLIGENCE_INCREMENTAL_SYNC = True
_MAX_HISTORY = 5000


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _record_identity(row: Mapping[str, Any]) -> str:
    for key in ('record_id', 'external_id', 'id', 'url', 'slug', 'title'):
        text = str(row.get(key) or '').strip()
        if text:
            return text
    return hashlib.sha256(repr(sorted(dict(row).items())).encode('utf-8', errors='replace')).hexdigest()


@dataclass(frozen=True)
class IncrementalSyncDiff:
    new_records: tuple[dict[str, Any], ...]
    changed_records: tuple[dict[str, Any], ...]
    unchanged_records: tuple[dict[str, Any], ...]
    cursor: ProviderCursor


@dataclass
class IncrementalSyncEngine:
    cursor_store: PersistentMarketIntelligenceCursorStore = field(default_factory=PersistentMarketIntelligenceCursorStore)

    def diff(
        self,
        *,
        tenant_id: str,
        provider: str,
        source_family: str,
        scope_key: str,
        records: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]],
    ) -> IncrementalSyncDiff:
        current = self.cursor_store.load(tenant_id=tenant_id, provider=provider, source_family=source_family, scope_key=scope_key)
        rows = tuple(self._normalize_row(item) for item in records if isinstance(item, Mapping))
        current_checksum = self._checksum(rows)
        new_records: list[dict[str, Any]] = []
        changed_records: list[dict[str, Any]] = []
        unchanged_records: list[dict[str, Any]] = []
        previous_seen = tuple(str(item).strip() for item in (current.metadata.get('seen_record_ids') or []) if str(item).strip())
        previous_hashes = {str(key): str(value) for key, value in dict(current.metadata.get('row_hashes') or {}).items() if str(key).strip()}
        previous_seen_set = set(previous_seen)
        updated_seen_ids: list[str] = []
        updated_hashes: dict[str, str] = {}
        for row in rows:
            record_id = _record_identity(row)
            row_hash = self._row_hash(row)
            updated_seen_ids.append(record_id)
            updated_hashes[record_id] = row_hash
            if record_id not in previous_seen_set:
                new_records.append(dict(row))
            elif previous_hashes.get(record_id) != row_hash:
                changed_records.append(dict(row))
            else:
                unchanged_records.append(dict(row))
        merged_ids = self._merge_seen_ids(previous_seen, updated_seen_ids)
        merged_hashes = self._merge_hashes(previous_hashes, updated_hashes, merged_ids)
        updated_cursor = ProviderCursor(
            tenant_id=tenant_id,
            provider=provider,
            source_family=source_family,
            scope_key=scope_key,
            cursor=(_record_identity(rows[-1]) if rows else current.cursor),
            last_seen_at=(self._last_seen_at(rows) or current.last_seen_at),
            checksum=current_checksum,
            updated_at=_utc_now().isoformat(),
            metadata={
                'seen_record_ids': list(merged_ids),
                'row_hashes': merged_hashes,
                'previous_checksum': current.checksum,
                'counts': {
                    'new': len(new_records),
                    'changed': len(changed_records),
                    'unchanged': len(unchanged_records),
                    'history_size': len(merged_ids),
                },
            },
        )
        self.cursor_store.save(updated_cursor)
        return IncrementalSyncDiff(
            new_records=tuple(new_records),
            changed_records=tuple(changed_records),
            unchanged_records=tuple(unchanged_records),
            cursor=updated_cursor,
        )

    def _normalize_row(self, row: Mapping[str, Any]) -> dict[str, Any]:
        normalized = _safe_dict(row)
        normalized['record_id'] = _record_identity(normalized)
        return normalized

    def _last_seen_at(self, rows: tuple[Mapping[str, Any], ...]) -> str | None:
        if not rows:
            return None
        return str(rows[-1].get('updated_at') or rows[-1].get('published_at') or rows[-1].get('observed_at') or '').strip() or None

    def _checksum(self, rows: tuple[Mapping[str, Any], ...]) -> str:
        digest = hashlib.sha256()
        for row in rows:
            digest.update(self._row_hash(row).encode('utf-8'))
        return digest.hexdigest()

    def _row_hash(self, row: Mapping[str, Any]) -> str:
        return hashlib.sha256(repr(sorted(dict(row).items())).encode('utf-8', errors='replace')).hexdigest()

    def _merge_seen_ids(self, previous_seen: tuple[str, ...], updated_seen: list[str]) -> tuple[str, ...]:
        ordered: list[str] = []
        seen: set[str] = set()
        for record_id in (*previous_seen, *updated_seen):
            if record_id and record_id not in seen:
                seen.add(record_id)
                ordered.append(record_id)
        return tuple(ordered[-_MAX_HISTORY:])

    def _merge_hashes(self, previous_hashes: dict[str, str], updated_hashes: dict[str, str], merged_ids: tuple[str, ...]) -> dict[str, str]:
        merged = dict(previous_hashes)
        merged.update(updated_hashes)
        allowed = set(merged_ids)
        return {record_id: value for record_id, value in merged.items() if record_id in allowed}


__all__ = ['CANON_MARKET_INTELLIGENCE_INCREMENTAL_SYNC', 'IncrementalSyncDiff', 'IncrementalSyncEngine']

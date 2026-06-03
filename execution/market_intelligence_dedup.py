from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any
from collections.abc import Iterable, Mapping


CANON_MARKET_INTELLIGENCE_DEDUP = True


@dataclass(frozen=True)
class MarketIntelligenceDeduplicator:
    def deduplicate(self, records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        output: list[dict[str, Any]] = []
        for item in records:
            record = dict(item or {})
            key = self._key_for(record)
            if not key or key in seen:
                continue
            seen.add(key)
            output.append(record)
        return output

    def _key_for(self, record: Mapping[str, Any]) -> str:
        provider = str(record.get('provider') or '').strip().lower()
        family = str(record.get('source_family') or '').strip().lower()
        external_id = str(record.get('external_id') or '').strip().lower()
        url = str(record.get('url') or '').strip().lower()
        dedup_hint = str(record.get('dedup_hint') or '').strip().lower()
        title = str(record.get('title') or '').strip().lower()
        raw = '|'.join((provider, family, external_id or url or dedup_hint or title))
        if raw.endswith('|'):
            return ''
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()


__all__ = ['CANON_MARKET_INTELLIGENCE_DEDUP', 'MarketIntelligenceDeduplicator']

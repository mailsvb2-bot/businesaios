from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any
from collections.abc import Mapping

from execution.market_intelligence_models import MarketIntelligenceIngestionRequest


CANON_MARKET_INTELLIGENCE_IDEMPOTENCY = True


def build_market_intelligence_idempotency_key(request: MarketIntelligenceIngestionRequest) -> str:
    payload = {
        'tenant_id': request.tenant_id,
        'source_family': request.source_family,
        'provider': request.provider,
        'action_type': request.action_type,
        'query': request.query,
        'subject_url': request.subject_url,
        'account_ref': request.account_ref,
        'region': request.region,
        'locale': request.locale,
        'limit': request.limit,
        'dry_run': request.dry_run,
        'metadata': dict(request.metadata or {}),
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


@dataclass
class MarketIntelligenceIdempotencyStore:
    max_entries: int = 1000
    _seen: dict[str, dict[str, Any]] = field(default_factory=dict)
    _order: list[str] = field(default_factory=list)

    def get(self, key: str) -> dict[str, Any] | None:
        value = self._seen.get(str(key))
        return copy.deepcopy(value) if isinstance(value, Mapping) else None

    def put(self, key: str, payload: Mapping[str, Any]) -> None:
        normalized_key = str(key)
        if normalized_key not in self._seen:
            self._order.append(normalized_key)
        self._seen[normalized_key] = copy.deepcopy(dict(payload or {}))
        while len(self._order) > int(self.max_entries):
            evicted = self._order.pop(0)
            self._seen.pop(evicted, None)

    def snapshot(self) -> dict[str, Any]:
        return {
            'entries': len(self._seen),
            'keys': list(self._order),
        }


__all__ = [
    'CANON_MARKET_INTELLIGENCE_IDEMPOTENCY',
    'MarketIntelligenceIdempotencyStore',
    'build_market_intelligence_idempotency_key',
]

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any
from collections.abc import Mapping

from runtime._internal.market_intelligence.state_store import SqliteMarketIntelligenceStateStore

CANON_MARKET_INTELLIGENCE_RECOVERY = True


@dataclass(frozen=True)
class RecoveryVerdict:
    allowed: bool
    reason: str
    replay_key: str
    resume_cursor: str | None = None
    quarantined: bool = False
    replay_hit: bool = False


@dataclass
class MarketIntelligenceRecoveryController:
    state_store: SqliteMarketIntelligenceStateStore = field(default_factory=SqliteMarketIntelligenceStateStore)

    def replay_key(self, *, tenant_id: str, provider: str, source_family: str, scope_key: str, operation: str, request_fingerprint: str) -> str:
        raw = '|'.join([tenant_id, provider, source_family, scope_key, operation, request_fingerprint])
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def preflight(self, *, tenant_id: str, provider: str, source_family: str, scope_key: str, operation: str, request_fingerprint: str) -> RecoveryVerdict:
        replay_key = self.replay_key(
            tenant_id=tenant_id,
            provider=provider,
            source_family=source_family,
            scope_key=scope_key,
            operation=operation,
            request_fingerprint=request_fingerprint,
        )
        if self.state_store.is_quarantined(tenant_id=tenant_id, provider=provider, source_family=source_family, scope_key=scope_key):
            return RecoveryVerdict(allowed=False, reason='source_quarantined', replay_key=replay_key, quarantined=True, replay_hit=False)
        replay_hit = self.state_store.has_successful_replay(tenant_id=tenant_id, provider=provider, source_family=source_family, scope_key=scope_key, replay_key=replay_key)
        checkpoint = self.state_store.load_checkpoint(tenant_id=tenant_id, provider=provider, source_family=source_family, scope_key=scope_key)
        return RecoveryVerdict(allowed=True, reason='resume_allowed', replay_key=replay_key, resume_cursor=checkpoint.cursor, quarantined=False, replay_hit=replay_hit)

    def quarantine_poisoned_source(self, *, tenant_id: str, provider: str, source_family: str, scope_key: str, reason_code: str, details: Mapping[str, Any] | None = None) -> None:
        self.state_store.quarantine_scope(tenant_id=tenant_id, provider=provider, source_family=source_family, scope_key=scope_key, reason_code=reason_code, details=details)

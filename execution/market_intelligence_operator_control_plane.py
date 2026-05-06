from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from execution.market_intelligence_operator_store import (
    PersistentMarketIntelligenceOperatorStore,
    ReviewQueueRecord,
)


CANON_MARKET_INTELLIGENCE_OPERATOR_CONTROL_PLANE = True


@dataclass
class MarketIntelligenceOperatorControlPlane:
    store: PersistentMarketIntelligenceOperatorStore = field(default_factory=PersistentMarketIntelligenceOperatorStore)

    def enqueue_review(self, *, tenant_id: str, provider: str, source_family: str, external_id: str, reason: str, payload: Mapping[str, Any]) -> str:
        review_id = self.store.allocate_review_id()
        item = ReviewQueueRecord(
            review_id=review_id,
            tenant_id=tenant_id,
            provider=provider,
            source_family=source_family,
            external_id=external_id,
            reason=reason,
            payload=dict(payload or {}),
        )
        self.store.put_review(item)
        self.store.add_audit(action='review_enqueued', payload={'review_id': review_id, 'reason': reason, 'provider': provider, 'external_id': external_id})
        return review_id


    def claim_review(self, *, review_id: str, operator_id: str) -> None:
        self.store.transition_review(review_id=review_id, status='in_review', operator_id=operator_id)
        self.store.add_audit(action='review_claimed', payload={'review_id': review_id, 'operator_id': operator_id})

    def escalate_review(self, *, review_id: str, operator_id: str | None, reason: str) -> None:
        self.store.transition_review(review_id=review_id, status='escalated', operator_id=operator_id)
        self.store.add_audit(action='review_escalated', payload={'review_id': review_id, 'operator_id': operator_id, 'reason': reason})

    def mark_false_positive(self, *, review_id: str, operator_id: str) -> None:
        self.store.resolve_review(review_id=review_id, resolution='false_positive', operator_id=operator_id)
        self.store.add_audit(action='false_positive', payload={'review_id': review_id, 'operator_id': operator_id})

    def mark_false_negative(self, *, review_id: str, operator_id: str) -> None:
        self.store.resolve_review(review_id=review_id, resolution='false_negative', operator_id=operator_id)
        self.store.add_audit(action='false_negative', payload={'review_id': review_id, 'operator_id': operator_id})

    def override(self, *, operator_id: str, action: str, tenant_id: str, provider: str, source_family: str, external_id: str, reason: str) -> None:
        self.store.add_audit(
            action='operator_override',
            payload={
                'operator_id': operator_id,
                'action': action,
                'tenant_id': tenant_id,
                'provider': provider,
                'source_family': source_family,
                'external_id': external_id,
                'reason': reason,
            },
        )

    def ban_source(self, *, tenant_id: str, provider: str, scope_key: str) -> None:
        self.store.add_ban(tenant_id=tenant_id, provider=provider, scope_key=scope_key)
        self.store.add_audit(action='source_banlist_add', payload={'tenant_id': tenant_id, 'provider': provider, 'scope_key': scope_key})

    def allow_source(self, *, tenant_id: str, provider: str, scope_key: str) -> None:
        self.store.add_allow(tenant_id=tenant_id, provider=provider, scope_key=scope_key)
        self.store.add_audit(action='source_allowlist_add', payload={'tenant_id': tenant_id, 'provider': provider, 'scope_key': scope_key})

    def check_source_allowed(self, *, tenant_id: str, provider: str, scope_key: str) -> None:
        if self.store.is_banned(tenant_id=tenant_id, provider=provider, scope_key=scope_key):
            raise ValueError(f'source blocked by operator banlist: {provider}/{scope_key}')

    def open_reviews(self, *, tenant_id: str | None = None) -> tuple[dict[str, Any], ...]:
        return tuple(item.as_dict() for item in self.store.list_reviews(tenant_id=tenant_id, open_only=True))

    def snapshot(self) -> dict[str, Any]:
        return self.store.snapshot()

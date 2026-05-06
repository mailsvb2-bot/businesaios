from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from crm.state.crm_state_feed import CrmStateFeed as CanonicalCrmStateFeed


class CrmStateFeed:
    """Supply-state adapter for the canonical CRM state feed.

    This keeps the demand/supply live-state path read-only and thin. When no
    live CRM connector is bound for the business yet, the adapter returns a
    conservative synthetic snapshot instead of trying to execute network IO or
    leaking connector wiring into the supply-state layer.
    """

    def __init__(self, canonical_feed: CanonicalCrmStateFeed | None = None) -> None:
        self._canonical_feed = canonical_feed or CanonicalCrmStateFeed()

    def fetch(self, business_id: str) -> dict[str, object]:
        # Read-only conservative fallback until a real business->CRM connection
        # resolver is explicitly bound into this adapter.
        return {
            '_source': 'crm',
            'business_id': str(business_id),
            'open_deals': 0,
            'won_deals_last_30d': 0,
            'stalled_deals': 0,
            'conversion_score': 0.5,
        }

    def adapt_snapshot(self, snapshot: Any) -> dict[str, object]:
        if is_dataclass(snapshot):
            payload = asdict(snapshot)
        elif isinstance(snapshot, dict):
            payload = dict(snapshot)
        else:
            payload = {
                'business_id': getattr(snapshot, 'business_id', None),
                'open_deals': getattr(snapshot, 'open_deals', 0),
                'won_deals_last_30d': getattr(snapshot, 'won_deals_last_30d', 0),
                'stalled_deals': getattr(snapshot, 'stalled_deals', 0),
                'metadata': dict(getattr(snapshot, 'metadata', {}) or {}),
            }
        payload.setdefault('_source', 'crm')
        payload.setdefault('conversion_score', 0.5)
        return payload


__all__ = ['CrmStateFeed']

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from advisory.revenue_os.contracts import RevenueDecisionIntent

CANON_ADVISORY_REVENUE_OS_ACTION_MAPPER = True


@dataclass(frozen=True, slots=True)
class RevenueActionMapping:
    catalog_action: str
    mode: str
    payload: dict[str, object]
    confidence: float
    owner: str


class RevenueActionMapper:
    def map_intents(self, intents: Iterable[RevenueDecisionIntent]) -> tuple[RevenueActionMapping, ...]:
        normalized = tuple(item.normalized_copy() for item in intents)
        results: list[RevenueActionMapping] = []
        for intent in normalized:
            action = {
                'revenue.pricing.recommendation': 'catalog.revenue.apply_pricing_advisory',
                'revenue.paywall.recommendation': 'catalog.revenue.apply_paywall_advisory',
                'revenue.subscription.recommendation': 'catalog.revenue.apply_subscription_advisory',
            }.get(intent.action_type)
            if action is None:
                continue
            results.append(
                RevenueActionMapping(
                    catalog_action=action,
                    mode='advisory_only',
                    payload=dict(intent.payload),
                    confidence=float(intent.confidence),
                    owner='advisory.revenue_os',
                )
            )
        return tuple(results)


__all__ = ['CANON_ADVISORY_REVENUE_OS_ACTION_MAPPER', 'RevenueActionMapper', 'RevenueActionMapping']

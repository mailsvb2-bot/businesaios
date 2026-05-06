from __future__ import annotations

from dataclasses import dataclass

CANON_ADVISORY_REVENUE_OS_FEATURE_FLAGS = True


@dataclass(frozen=True, slots=True)
class RevenueFeatureFlags:
    pricing: bool = True
    paywalls: bool = True
    subscriptions: bool = True
    experiments: bool = True

    @classmethod
    def from_policy(cls, *, pricing: bool, paywall: bool, subscriptions: bool, experiments: bool) -> 'RevenueFeatureFlags':
        return cls(pricing=pricing, paywalls=paywall, subscriptions=subscriptions, experiments=experiments)


__all__ = ['CANON_ADVISORY_REVENUE_OS_FEATURE_FLAGS', 'RevenueFeatureFlags']

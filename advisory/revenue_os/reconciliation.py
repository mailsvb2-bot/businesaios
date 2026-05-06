from __future__ import annotations

from dataclasses import dataclass, replace

from advisory.revenue_os.contracts import _required_text

CANON_ADVISORY_REVENUE_OS_RECONCILIATION = True


@dataclass(frozen=True, slots=True)
class RevenueProviderTruth:
    product_id: str
    net_revenue: float
    refunds: int
    active_subscribers: int

    def normalized_copy(self) -> 'RevenueProviderTruth':
        net_revenue = round(float(self.net_revenue), 6)
        refunds = int(self.refunds)
        active_subscribers = int(self.active_subscribers)
        if net_revenue < 0.0:
            raise ValueError('net_revenue must be >= 0')
        if refunds < 0:
            raise ValueError('refunds must be >= 0')
        if active_subscribers < 0:
            raise ValueError('active_subscribers must be >= 0')
        return replace(
            self,
            product_id=_required_text(self.product_id, field_name='product_id'),
            net_revenue=net_revenue,
            refunds=refunds,
            active_subscribers=active_subscribers,
        )


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    net_revenue_delta: float
    refunds_delta: int
    subscribers_delta: int
    severity: str


class RevenueReconciliationContract:
    def reconcile(self, *, internal: RevenueProviderTruth, provider: RevenueProviderTruth) -> ReconciliationResult:
        normalized_internal = internal.normalized_copy()
        normalized_provider = provider.normalized_copy()
        if normalized_internal.product_id != normalized_provider.product_id:
            raise ValueError('product_id mismatch')
        net_revenue_delta = round(normalized_provider.net_revenue - normalized_internal.net_revenue, 6)
        refunds_delta = normalized_provider.refunds - normalized_internal.refunds
        subscribers_delta = normalized_provider.active_subscribers - normalized_internal.active_subscribers
        max_signal = max(abs(net_revenue_delta), abs(float(refunds_delta)), abs(float(subscribers_delta)))
        severity = 'high' if max_signal >= 100.0 else 'moderate' if max_signal >= 10.0 else 'low'
        return ReconciliationResult(
            net_revenue_delta=net_revenue_delta,
            refunds_delta=refunds_delta,
            subscribers_delta=subscribers_delta,
            severity=severity,
        )


__all__ = ['CANON_ADVISORY_REVENUE_OS_RECONCILIATION', 'ReconciliationResult', 'RevenueProviderTruth', 'RevenueReconciliationContract']

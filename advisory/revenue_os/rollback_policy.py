from __future__ import annotations

from dataclasses import dataclass

from advisory.revenue_os.contracts import RevenueSnapshot

CANON_ADVISORY_REVENUE_OS_ROLLBACK_POLICY = True


@dataclass(frozen=True, slots=True)
class RollbackDecision:
    should_rollback: bool
    reason_codes: tuple[str, ...]


class RevenueRollbackPolicy:
    def __init__(self, *, minimum_sample_conversions: int = 20) -> None:
        self._minimum_sample_conversions = int(minimum_sample_conversions)
        if self._minimum_sample_conversions <= 0:
            raise ValueError('minimum_sample_conversions must be > 0')

    def evaluate(self, *, baseline: RevenueSnapshot, observed: RevenueSnapshot) -> RollbackDecision:
        base = baseline.normalized_copy()
        current = observed.normalized_copy()
        reasons: list[str] = []
        if current.conversions < self._minimum_sample_conversions:
            return RollbackDecision(should_rollback=False, reason_codes=('insufficient_sample',))
        if current.churn_rate - base.churn_rate >= 0.03:
            reasons.append('churn_regression')
        if current.refund_rate - base.refund_rate >= 0.03:
            reasons.append('refund_regression')
        if base.conversion_rate - current.conversion_rate >= 0.03:
            reasons.append('conversion_regression')
        if base.net_revenue > 0 and ((base.net_revenue - current.net_revenue) / base.net_revenue) >= 0.10:
            reasons.append('net_revenue_regression')
        return RollbackDecision(should_rollback=bool(reasons), reason_codes=tuple(sorted(reasons)))


__all__ = ['CANON_ADVISORY_REVENUE_OS_ROLLBACK_POLICY', 'RevenueRollbackPolicy', 'RollbackDecision']

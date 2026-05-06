from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Sequence

from advisory.revenue_os.contracts import RevenueSnapshot, _required_text

CANON_ADVISORY_REVENUE_OS_WORLD_STATE = True


@dataclass(frozen=True, slots=True)
class RevenueWorldState:
    tenant_id: str
    product_id: str
    snapshot_count: int
    metrics: dict[str, float]

    def to_dict(self) -> dict[str, object]:
        return {
            'tenant_id': self.tenant_id,
            'product_id': self.product_id,
            'snapshot_count': self.snapshot_count,
            'metrics': dict(self.metrics),
        }


class RevenueWorldStateBuilder:
    def build(
        self,
        *,
        tenant_id: str,
        product_id: str,
        snapshots: Sequence[RevenueSnapshot],
    ) -> RevenueWorldState:
        normalized = tuple(item.normalized_copy() for item in snapshots)
        if not normalized:
            raise ValueError('at least one revenue snapshot is required')
        latest = normalized[-1]
        return RevenueWorldState(
            tenant_id=_required_text(tenant_id, field_name='tenant_id'),
            product_id=_required_text(product_id, field_name='product_id'),
            snapshot_count=len(normalized),
            metrics={
                'conversion_rate': round(latest.conversion_rate, 6),
                'conversion_rate_trailing_mean': round(fmean(item.conversion_rate for item in normalized), 6),
                'trial_start_rate': round(latest.trial_start_rate, 6),
                'trial_to_paid_rate': round(latest.trial_to_paid_rate, 6),
                'churn_rate': round(latest.churn_rate, 6),
                'churn_rate_trailing_mean': round(fmean(item.churn_rate for item in normalized), 6),
                'refund_rate': round(latest.refund_rate, 6),
                'refund_rate_trailing_mean': round(fmean(item.refund_rate for item in normalized), 6),
                'average_revenue_per_user': round(latest.arpu, 6),
                'average_revenue_per_user_trailing_mean': round(fmean(item.arpu for item in normalized), 6),
                'contribution_margin': round(latest.contribution_margin, 6),
                'contribution_margin_trailing_mean': round(fmean(item.contribution_margin for item in normalized), 6),
                'net_revenue': round(latest.net_revenue, 6),
                'gross_revenue': round(latest.gross_revenue, 6),
                'acquisition_spend': round(latest.acquisition_spend, 6),
                'active_subscribers': float(latest.active_subscribers),
                'trial_subscribers': float(latest.trial_subscribers),
            },
        )


__all__ = ['CANON_ADVISORY_REVENUE_OS_WORLD_STATE', 'RevenueWorldState', 'RevenueWorldStateBuilder']

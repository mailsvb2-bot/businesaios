from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Sequence

from advisory.revenue_os.contracts import RevenueSnapshot

CANON_ADVISORY_REVENUE_OS_LTV_MODEL = True


@dataclass(frozen=True, slots=True)
class LTVProjection:
    predicted_ltv: float
    payback_days: float
    confidence: float

    def to_dict(self) -> dict[str, float]:
        return {
            'predicted_ltv': self.predicted_ltv,
            'payback_days': self.payback_days,
            'confidence': self.confidence,
        }


class LTVModel:
    def project(self, snapshots: Sequence[RevenueSnapshot], *, target_cac: float | None = None) -> LTVProjection:
        normalized = tuple(item.normalized_copy() for item in snapshots)
        if not normalized:
            raise ValueError('at least one revenue snapshot is required')
        arpu = fmean(item.arpu for item in normalized)
        churn = max(0.01, fmean(item.churn_rate for item in normalized))
        gross_to_net = fmean(0.0 if item.gross_revenue <= 0 else item.net_revenue / item.gross_revenue for item in normalized)
        predicted_ltv = round(arpu * gross_to_net * (1.0 / churn), 6)
        basis_cac = float(target_cac) if target_cac is not None else fmean(
            0.0 if item.conversions <= 0 else item.acquisition_spend / item.conversions for item in normalized
        )
        payback_days = 0.0 if arpu <= 0 else round((basis_cac / arpu) * 30.0, 6)
        confidence = round(min(1.0, len(normalized) / 12.0), 6)
        return LTVProjection(predicted_ltv=predicted_ltv, payback_days=payback_days, confidence=confidence)


__all__ = ['CANON_ADVISORY_REVENUE_OS_LTV_MODEL', 'LTVModel', 'LTVProjection']

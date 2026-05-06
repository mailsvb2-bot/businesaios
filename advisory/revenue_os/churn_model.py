from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Sequence

from advisory.revenue_os.contracts import RevenueSnapshot

CANON_ADVISORY_REVENUE_OS_CHURN_MODEL = True


@dataclass(frozen=True, slots=True)
class ChurnProjection:
    churn_rate: float
    risk_band: str
    evidence_strength: float

    def to_dict(self) -> dict[str, float | str]:
        return {
            'churn_rate': self.churn_rate,
            'risk_band': self.risk_band,
            'evidence_strength': self.evidence_strength,
        }


class ChurnModel:
    def project(self, snapshots: Sequence[RevenueSnapshot]) -> ChurnProjection:
        normalized = tuple(item.normalized_copy() for item in snapshots)
        if not normalized:
            raise ValueError('at least one revenue snapshot is required')
        latest = normalized[-1].churn_rate
        trailing = fmean(item.churn_rate for item in normalized)
        refund_penalty = fmean(item.refund_rate for item in normalized)
        projected = round(min(1.0, (0.60 * latest) + (0.30 * trailing) + (0.10 * refund_penalty)), 6)
        risk_band = 'critical' if projected >= 0.12 else 'elevated' if projected >= 0.07 else 'stable'
        evidence_strength = round(min(1.0, len(normalized) / 10.0), 6)
        return ChurnProjection(churn_rate=projected, risk_band=risk_band, evidence_strength=evidence_strength)


__all__ = ['CANON_ADVISORY_REVENUE_OS_CHURN_MODEL', 'ChurnModel', 'ChurnProjection']

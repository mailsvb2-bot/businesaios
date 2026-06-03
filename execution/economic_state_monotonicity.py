from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from collections.abc import Mapping

CANON_ECONOMIC_STATE_MONOTONICITY = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_rows(value: object) -> list[dict[str, Any]]:
    return [_safe_dict(item) for item in value or ()]


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _current_meta(current_state: Mapping[str, Any] | None) -> dict[str, Any]:
    cur = _safe_dict(current_state)
    meta = _safe_dict(cur.get('meta'))
    return meta


def _verified_revenue_total_from_payload(payload: Mapping[str, Any]) -> float:
    total = 0.0
    for row in _safe_rows(payload.get('feedback_rows')):
        if bool(row.get('verified')):
            total += _safe_float(row.get('realized_revenue') or row.get('revenue_amount'))
    for row in _safe_rows(payload.get('roi_rows')):
        total += max(0.0, _safe_float(row.get('revenue_amount')))
    return total


def _verified_feedback_count_from_payload(payload: Mapping[str, Any]) -> int:
    return sum(1 for row in _safe_rows(payload.get('feedback_rows')) if bool(row.get('verified')))


@dataclass(frozen=True, slots=True)
class EconomicStateMonotonicityVerdict:
    valid: bool
    current_verified_revenue_total: float
    incoming_verified_revenue_total: float
    current_verified_feedback_count: int
    incoming_verified_feedback_count: int
    reason: str = 'economic_state_monotonic'
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'valid': bool(self.valid),
            'current_verified_revenue_total': float(self.current_verified_revenue_total),
            'incoming_verified_revenue_total': float(self.incoming_verified_revenue_total),
            'current_verified_feedback_count': int(self.current_verified_feedback_count),
            'incoming_verified_feedback_count': int(self.incoming_verified_feedback_count),
            'reason': self.reason,
            'metadata': dict(self.metadata),
        }


class EconomicStateMonotonicityGuard:
    def validate(
        self,
        *,
        current_state: Mapping[str, Any] | None,
        incoming_payload: Mapping[str, Any] | None,
    ) -> EconomicStateMonotonicityVerdict:
        meta = _current_meta(current_state)
        payload = _safe_dict(incoming_payload)
        current_feedback_history = _safe_rows(meta.get('economic_feedback_history'))
        current_verified_feedback_count = sum(1 for row in current_feedback_history if bool(row.get('verified')))
        current_verified_revenue_total = sum(_safe_float(row.get('realized_revenue') or row.get('revenue_amount')) for row in current_feedback_history if bool(row.get('verified')))
        incoming_verified_feedback_count = _verified_feedback_count_from_payload(payload)
        incoming_verified_revenue_total = _verified_revenue_total_from_payload(payload)

        valid = True
        reason = 'economic_state_monotonic'
        if incoming_verified_feedback_count < current_verified_feedback_count:
            valid = False
            reason = 'economic_verified_feedback_rollback'
        elif incoming_verified_revenue_total + 1e-9 < current_verified_revenue_total:
            valid = False
            reason = 'economic_verified_revenue_rollback'

        return EconomicStateMonotonicityVerdict(
            valid=valid,
            current_verified_revenue_total=current_verified_revenue_total,
            incoming_verified_revenue_total=incoming_verified_revenue_total,
            current_verified_feedback_count=current_verified_feedback_count,
            incoming_verified_feedback_count=incoming_verified_feedback_count,
            reason=reason,
            metadata={'owner': 'execution.economic_state_monotonicity'},
        )


__all__ = [
    'CANON_ECONOMIC_STATE_MONOTONICITY',
    'EconomicStateMonotonicityVerdict',
    'EconomicStateMonotonicityGuard',
]

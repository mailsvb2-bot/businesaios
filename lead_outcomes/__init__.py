from __future__ import annotations

"""Lead-outcome state surface.

This namespace owns mutable request/lead outcome state, canonical field tracking,
and outcome timeline mutation. It must remain the single writable business-outcome
truth and must not become a second attribution/provenance model layer.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from registry.base_registry import BaseRegistry

CANON_LEAD_OUTCOME_STATE_NAMESPACE = True

@dataclass(frozen=True)
class VerificationEvidence:
    kind: str
    value: object
    weight: float = 1.0

    def normalized_weight(self) -> float:
        return max(0.0, min(1.0, float(self.weight)))

@dataclass(frozen=True)
class VerificationDecision:
    verified: bool
    confidence: float
    reasons: tuple[str, ...]

class OutcomeVerifier:
    def verify(self, evidences: Iterable[VerificationEvidence]) -> VerificationDecision:
        items = list(evidences)
        if not items:
            return VerificationDecision(False, 0.0, ('no_evidence',))
        score = 0.0
        reasons: list[str] = []
        for item in items:
            if item.kind in {'call_connected', 'booking_confirmed', 'crm_synced', 'payment_seen'} and bool(item.value):
                score += item.normalized_weight()
                reasons.append(item.kind)
        confidence = min(1.0, round(score / max(1.0, len(items)), 4))
        return VerificationDecision(score >= 1.0, confidence, tuple(reasons or ['insufficient_positive_evidence']))

class OutcomeMutation:
    """Single mutation primitive for lead outcome rows.

    Domain trackers stay as thin adapters, while actual registry mutation logic
    lives in one place so semantics do not drift across modules.
    """

    def set_fields(self, registry: Any, request_id: str, **fields: object) -> None:
        registry.update(str(request_id), dict(fields))

class FieldTracker:
    """Single update primitive for thin domain outcome trackers."""

    def __init__(self, *, field_name: str, coercer: Callable[[Any], object]) -> None:
        normalized = str(field_name).strip()
        if not normalized:
            raise ValueError('field_name must be non-empty')
        self._field_name = normalized
        self._coercer = coercer
        self._mutation = OutcomeMutation()

    def update(self, registry: Any, request_id: str, value: Any) -> None:
        self._mutation.set_fields(registry, request_id, **{self._field_name: self._coercer(value)})

class LeadContactTracker(FieldTracker):
    def __init__(self) -> None:
        super().__init__(field_name='contacted', coercer=bool)

class LeadConversionTracker(FieldTracker):
    def __init__(self) -> None:
        super().__init__(field_name='converted', coercer=bool)

class LeadLossTracker(FieldTracker):
    def __init__(self) -> None:
        super().__init__(field_name='loss_reason', coercer=str)

class LeadResponseTracker(FieldTracker):
    def __init__(self) -> None:
        super().__init__(field_name='responded', coercer=bool)

class LeadReturnTracker(FieldTracker):
    def __init__(self) -> None:
        super().__init__(field_name='returned', coercer=bool)

class LeadRevenueTracker(FieldTracker):
    def __init__(self) -> None:
        super().__init__(field_name='revenue', coercer=float)

class LeadStatusTracker(FieldTracker):
    def __init__(self) -> None:
        super().__init__(field_name='status', coercer=str)

class LeadOutcomeRegistry(BaseRegistry):
    def __init__(self) -> None:
        super().__init__(kind='lead_outcome')

    def has(self, request_id: str) -> bool:
        return str(request_id) in self.snapshot()

    def update(self, request_id: str, payload: dict[str, object]) -> None:
        current = self.get(request_id) if self.has(request_id) else {}
        row = dict(current)
        row.update(dict(payload))
        self.register(str(request_id), row)

    def get(self, request_id: str) -> dict[str, object]:
        try:
            row = super().get(str(request_id))
        except KeyError:
            return {}
        return dict(row if isinstance(row, dict) else {})

    def require(self, request_id: str) -> dict[str, object]:
        row = self.get(request_id)
        if not row:
            raise KeyError(str(request_id))
        return row

class OutcomeTimeline:
    @staticmethod
    def _load_row(store: object, request_id: str) -> dict[str, object]:
        require = getattr(store, 'require', None)
        if callable(require):
            try:
                row = require(request_id)
            except KeyError:
                row = {}
            return dict(row if isinstance(row, Mapping) else {})

        fetch = getattr(store, 'fetch', None)
        if callable(fetch):
            row = fetch(request_id)
            return dict(row if isinstance(row, Mapping) else {})

        read = getattr(store, 'read', None)
        if callable(read):
            row = read(request_id)
            return dict(row if isinstance(row, Mapping) else {})

        getitem = getattr(store, '__getitem__', None)
        if callable(getitem):
            try:
                row = getitem(request_id)
            except KeyError:
                row = {}
            return dict(row if isinstance(row, Mapping) else {})

        raise TypeError('outcome timeline store must expose require/fetch/read/__getitem__')

    def append(self, registry, request_id: str, event: str) -> None:
        row = self._load_row(registry, request_id)
        timeline = list(row.get('timeline') or [])
        timeline.append(str(event))
        registry.update(request_id, {'timeline': timeline})

class OutcomeExplainer:
    def explain(self, row: dict[str, object]) -> tuple[str, ...]:
        return tuple(f"{k}={v}" for k, v in sorted(row.items()))

__all__ = [
    'CANON_LEAD_OUTCOME_STATE_NAMESPACE',
    'FieldTracker',
    'LeadContactTracker',
    'LeadConversionTracker',
    'LeadLossTracker',
    'LeadOutcomeRegistry',
    'LeadResponseTracker',
    'LeadReturnTracker',
    'LeadRevenueTracker',
    'LeadStatusTracker',
    'OutcomeExplainer',
    'OutcomeMutation',
    'OutcomeTimeline',
    'OutcomeVerifier',
    'VerificationDecision',
    'VerificationEvidence',
]

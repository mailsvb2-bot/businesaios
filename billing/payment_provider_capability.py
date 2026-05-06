from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Mapping


CANON_BILLING_PAYMENT_PROVIDER_CAPABILITY = True
ALLOWED_PROVIDER_OPERATIONS = frozenset({'ensure_customer', 'collect', 'refund'})


@dataclass(frozen=True)
class PaymentProviderCapabilities:
    operations: tuple[str, ...] = ('ensure_customer', 'collect', 'refund')
    strict_affinity_for_refund: bool = False
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        normalized_ops = tuple(str(item).strip().lower() for item in self.operations)
        if any(not item for item in normalized_ops):
            raise ValueError('operations cannot contain blank values')
        if len(set(normalized_ops)) != len(normalized_ops):
            raise ValueError('operations must be unique')
        unknown = set(normalized_ops) - set(ALLOWED_PROVIDER_OPERATIONS)
        if unknown:
            raise ValueError(f'unsupported operations: {sorted(unknown)}')

    def normalized_copy(self) -> 'PaymentProviderCapabilities':
        self.validate()
        return replace(
            self,
            operations=tuple(sorted({str(item).strip().lower() for item in self.operations})),
            strict_affinity_for_refund=bool(self.strict_affinity_for_refund),
            metadata=dict(self.metadata),
        )

    def supports(self, operation: str) -> bool:
        normalized = self.normalized_copy()
        op = str(operation or '').strip().lower()
        if not op:
            raise ValueError('operation is required')
        return op in set(normalized.operations)


__all__ = [
    'ALLOWED_PROVIDER_OPERATIONS',
    'CANON_BILLING_PAYMENT_PROVIDER_CAPABILITY',
    'PaymentProviderCapabilities',
]

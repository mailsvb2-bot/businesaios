from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field, replace
from typing import Any

CANON_BILLING_PAYMENT_PROVIDER_CAPABILITY = True
ALLOWED_PROVIDER_OPERATIONS = frozenset({"ensure_customer", "collect", "refund"})


def _require_mapping(name: str, value: Any) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    return value


@dataclass(frozen=True)
class PaymentProviderCapabilities:
    operations: tuple[str, ...] = ("ensure_customer", "collect", "refund")
    strict_affinity_for_refund: bool = False
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if not isinstance(self.operations, tuple):
            raise ValueError("operations must be a tuple")
        normalized_ops: list[str] = []
        for item in self.operations:
            if not isinstance(item, str):
                raise ValueError("operations must contain strings")
            normalized = item.strip().lower()
            if not normalized:
                raise ValueError("operations cannot contain blank values")
            normalized_ops.append(normalized)
        if len(set(normalized_ops)) != len(normalized_ops):
            raise ValueError("operations must be unique")
        unknown = set(normalized_ops) - set(ALLOWED_PROVIDER_OPERATIONS)
        if unknown:
            raise ValueError(f"unsupported operations: {sorted(unknown)}")
        if not isinstance(self.strict_affinity_for_refund, bool):
            raise ValueError("strict_affinity_for_refund must be a boolean")
        _require_mapping("metadata", self.metadata)

    def normalized_copy(self) -> PaymentProviderCapabilities:
        self.validate()
        return replace(
            self,
            operations=tuple(sorted(item.strip().lower() for item in self.operations)),
            metadata=deepcopy(dict(self.metadata)),
        )

    def supports(self, operation: str) -> bool:
        normalized = self.normalized_copy()
        if not isinstance(operation, str):
            raise ValueError("operation must be a string")
        op = operation.strip().lower()
        if not op:
            raise ValueError("operation is required")
        return op in set(normalized.operations)


__all__ = [
    "ALLOWED_PROVIDER_OPERATIONS",
    "CANON_BILLING_PAYMENT_PROVIDER_CAPABILITY",
    "PaymentProviderCapabilities",
]

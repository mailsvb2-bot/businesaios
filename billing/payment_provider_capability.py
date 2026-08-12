from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field, replace
from typing import Any

CANON_BILLING_PAYMENT_PROVIDER_CAPABILITY = True
ALLOWED_PROVIDER_OPERATIONS = frozenset({"ensure_customer", "checkout", "status", "collect", "refund"})


def _require_mapping(name: str, value: Any) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    return value


def _normalized_operations(value: object) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise ValueError("operations must be a tuple")
    if any(not isinstance(item, str) for item in value):
        raise ValueError("operations must contain strings")
    operations = tuple(item.strip().lower() for item in value)
    if any(not item for item in operations):
        raise ValueError("operations cannot contain blank values")
    if len(set(operations)) != len(operations):
        raise ValueError("operations must be unique")
    unknown = set(operations) - ALLOWED_PROVIDER_OPERATIONS
    if unknown:
        raise ValueError(f"unsupported operations: {sorted(unknown)}")
    return tuple(sorted(operations))


@dataclass(frozen=True)
class PaymentProviderCapabilities:
    operations: tuple[str, ...] = ("ensure_customer", "collect", "refund")
    strict_affinity_for_refund: bool = False
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        _normalized_operations(self.operations)
        if not isinstance(self.strict_affinity_for_refund, bool):
            raise ValueError("strict_affinity_for_refund must be a boolean")
        _require_mapping("metadata", self.metadata)

    def normalized_copy(self) -> PaymentProviderCapabilities:
        self.validate()
        return replace(self, operations=_normalized_operations(self.operations), metadata=deepcopy(dict(self.metadata)))

    def supports(self, operation: str) -> bool:
        if not isinstance(operation, str):
            raise ValueError("operation must be a string")
        operation = operation.strip().lower()
        if not operation:
            raise ValueError("operation is required")
        return operation in self.normalized_copy().operations


__all__ = ["ALLOWED_PROVIDER_OPERATIONS", "CANON_BILLING_PAYMENT_PROVIDER_CAPABILITY", "PaymentProviderCapabilities"]
"""Payment provider ports.

SECURITY:
- This module MUST NOT import network libraries.
- Runtime implements the actual provider I/O inside runtime/_internal/_effects_impl.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class PaymentProviderPort(Protocol):
    def create_payment(
        self,
        *,
        amount: int,
        currency: str,
        order_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> str: ...

    def get_payment_status(self, *, external_payment_id: str) -> str: ...


def idempotence_key_for_order(order_id: str) -> str:
    """Canonical idempotence key for provider create.

    Must be stable across retries.
    """

    oid = str(order_id).strip()
    if not oid:
        raise ValueError("EMPTY_ORDER_ID")
    return f"order-{oid}"


@dataclass(frozen=True)
class PaymentStatus:
    external_id: str
    status: str


class PaymentProviderUnavailable(RuntimeError):
    """Raised when payment provider is unavailable (circuit breaker open)."""


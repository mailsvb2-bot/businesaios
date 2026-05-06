from __future__ import annotations

from execution.primitives import SetIdempotencyGate


class LeadDeliveryIdempotency:
    def __init__(self) -> None:
        self._gate = SetIdempotencyGate()

    def claim(self, request_id: str, business_id: str) -> bool:
        return self._gate.claim(f'{request_id}:{business_id}')

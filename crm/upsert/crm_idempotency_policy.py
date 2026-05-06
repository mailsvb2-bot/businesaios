from __future__ import annotations


class CrmIdempotencyPolicy:
    def ensure(self, idempotency_key: str) -> str:
        stable = str(idempotency_key or '').strip()
        if not stable:
            raise ValueError('CRM idempotency key is required')
        return stable

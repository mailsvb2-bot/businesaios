from __future__ import annotations


class CrmProviderIdempotency:
    def headers(self, idempotency_key: str) -> dict[str, str]:
        return {'Idempotency-Key': str(idempotency_key)}

from __future__ import annotations


class CrmRequestSigningPolicy:
    def headers(self, *, signature: str) -> dict[str, str]:
        return {'X-CRM-Signature': signature}

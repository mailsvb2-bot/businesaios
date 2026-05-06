from __future__ import annotations


class CrmSecretBinding:
    def bind(self, *, provider_key: str, secret_ref: str) -> dict[str, str]:
        return {'provider_key': provider_key, 'secret_ref': secret_ref}

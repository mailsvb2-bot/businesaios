from __future__ import annotations


class CrmTokenBindingPolicy:
    def bind(self, *, provider_key: str, token_ref: str) -> dict[str, str]:
        return {'provider_key': provider_key, 'token_ref': token_ref}

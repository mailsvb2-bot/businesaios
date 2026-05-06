from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Protocol

from crm.providers.common.crm_credentials import CrmAccessToken
from security.secret_contract import SecretRecord, SecretRef, SecretSource
from security.secret_vault import SecretVault, build_default_secret_vault


class CrmOAuthTokenStore(Protocol):
    def load(self, *, provider_key: str, secret_ref: str) -> CrmAccessToken | None: ...
    def save(self, *, provider_key: str, secret_ref: str, token: CrmAccessToken) -> None: ...
    def delete(self, *, provider_key: str, secret_ref: str) -> None: ...


class InMemoryCrmOAuthTokenStore:
    def __init__(self) -> None:
        self._tokens: dict[tuple[str, str], CrmAccessToken] = {}

    def load(self, *, provider_key: str, secret_ref: str) -> CrmAccessToken | None:
        return self._tokens.get((provider_key, secret_ref))

    def save(self, *, provider_key: str, secret_ref: str, token: CrmAccessToken) -> None:
        self._tokens[(provider_key, secret_ref)] = token

    def delete(self, *, provider_key: str, secret_ref: str) -> None:
        self._tokens.pop((provider_key, secret_ref), None)


class SecretVaultBackedCrmOAuthTokenStore:
    def __init__(self, *, vault: SecretVault | None = None) -> None:
        self._vault = vault or build_default_secret_vault()

    @property
    def vault(self) -> SecretVault:
        return self._vault

    def load(self, *, provider_key: str, secret_ref: str) -> CrmAccessToken | None:
        ref = self._secret_ref(provider_key=provider_key, secret_ref=secret_ref)
        try:
            payload = self._vault.get(ref)
        except (KeyError, RuntimeError):
            return None
        try:
            data = json.loads(payload.decode('utf-8'))
            return CrmAccessToken.from_dict(data)
        except (UnicodeDecodeError, JSONDecodeError, TypeError, ValueError):
            return None

    def save(self, *, provider_key: str, secret_ref: str, token: CrmAccessToken) -> None:
        ref = self._secret_ref(provider_key=provider_key, secret_ref=secret_ref)
        record = SecretRecord(
            ref=ref,
            ciphertext=b'pending',
            source=SecretSource.CONNECTOR,
            metadata={'provider_key': provider_key, 'secret_ref': secret_ref, 'kind': 'crm_oauth_token'},
        )
        self._vault.put(record, plaintext=json.dumps(token.to_dict(), sort_keys=True).encode('utf-8'))

    def delete(self, *, provider_key: str, secret_ref: str) -> None:
        ref = self._secret_ref(provider_key=provider_key, secret_ref=secret_ref)
        try:
            self._vault.deactivate(ref)
        except KeyError:
            return

    @staticmethod
    def _secret_ref(*, provider_key: str, secret_ref: str) -> SecretRef:
        return SecretRef(
            tenant_id='crm-oauth',
            connector_id=provider_key,
            scope='oauth-token',
            secret_name=secret_ref.replace(':', '__').replace('/', '_'),
            version='current',
        )

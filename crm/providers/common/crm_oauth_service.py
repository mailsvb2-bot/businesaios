from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Mapping

from crm.providers.common.crm_credentials import CrmAccessToken
from crm.providers.common.crm_http_client import CrmHttpClient, CrmHttpRequest
from crm.providers.common.crm_oauth_token_store import CrmOAuthTokenStore


@dataclass(frozen=True)
class CrmOAuthProviderConfig:
    provider_key: str
    token_url: str
    client_id: str
    client_secret: str


class CrmOAuthService:
    def __init__(self, *, http_client_factory: Callable[[str], CrmHttpClient], token_store: CrmOAuthTokenStore) -> None:
        self._http_client_factory = http_client_factory
        self._token_store = token_store

    def exchange_code(self, *, config: CrmOAuthProviderConfig, secret_ref: str, authorization_code: str, redirect_uri: str) -> CrmAccessToken:
        client = self._http_client_factory(config.token_url)
        response = client.send(CrmHttpRequest(method='POST', path='', form_body={
            'grant_type': 'authorization_code',
            'client_id': config.client_id,
            'client_secret': config.client_secret,
            'redirect_uri': redirect_uri,
            'code': authorization_code,
        }, timeout_seconds=20.0))
        token = self._token_from_payload(response.json_body if isinstance(response.json_body, Mapping) else {})
        self._token_store.save(provider_key=config.provider_key, secret_ref=secret_ref, token=token)
        return token

    def ensure_active_token(self, *, config: CrmOAuthProviderConfig, secret_ref: str) -> CrmAccessToken:
        token = self._token_store.load(provider_key=config.provider_key, secret_ref=secret_ref)
        if token is None:
            raise RuntimeError(f'No OAuth token bound for provider={config.provider_key} secret_ref={secret_ref}')
        if not token.is_expired():
            return token
        if not token.refresh_token:
            raise RuntimeError(f'Expired OAuth token for provider={config.provider_key} without refresh_token')
        refreshed = self.refresh_token(config=config, secret_ref=secret_ref, refresh_token=token.refresh_token)
        self._token_store.save(provider_key=config.provider_key, secret_ref=secret_ref, token=refreshed)
        return refreshed


    def revoke_binding(self, *, config: CrmOAuthProviderConfig, secret_ref: str) -> None:
        self._token_store.delete(provider_key=config.provider_key, secret_ref=secret_ref)

    def refresh_token(self, *, config: CrmOAuthProviderConfig, secret_ref: str, refresh_token: str) -> CrmAccessToken:
        client = self._http_client_factory(config.token_url)
        response = client.send(CrmHttpRequest(method='POST', path='', form_body={
            'grant_type': 'refresh_token',
            'client_id': config.client_id,
            'client_secret': config.client_secret,
            'refresh_token': refresh_token,
        }, timeout_seconds=20.0))
        payload = response.json_body if isinstance(response.json_body, Mapping) else {}
        token = self._token_from_payload(payload, default_refresh_token=refresh_token)
        self._token_store.save(provider_key=config.provider_key, secret_ref=secret_ref, token=token)
        return token

    @staticmethod
    def _token_from_payload(payload: Mapping[str, object], default_refresh_token: str | None = None) -> CrmAccessToken:
        access_token = str(payload.get('access_token') or '').strip()
        if not access_token:
            raise RuntimeError('OAuth exchange did not return access_token')
        expires_in_raw = payload.get('expires_in')
        try:
            expires_in = int(expires_in_raw) if expires_in_raw is not None else None
        except (TypeError, ValueError):
            expires_in = None
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in) if expires_in else None
        scope_raw = payload.get('scope')
        if isinstance(scope_raw, str):
            scope = tuple(item for item in scope_raw.replace(',', ' ').split() if item)
        elif isinstance(scope_raw, (list, tuple)):
            scope = tuple(str(item) for item in scope_raw if str(item).strip())
        else:
            scope = ()
        return CrmAccessToken(
            access_token=access_token,
            token_type=str(payload.get('token_type') or 'Bearer'),
            expires_at=expires_at,
            refresh_token=str(payload.get('refresh_token') or default_refresh_token or '') or None,
            scope=scope,
            metadata={k: v for k, v in payload.items() if k not in {'access_token', 'refresh_token'}},
        )

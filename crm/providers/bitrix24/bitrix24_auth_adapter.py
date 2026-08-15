from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone

from crm.providers.bitrix24.bitrix24_api_config import Bitrix24ApiConfig
from crm.providers.bitrix24.bitrix24_client import Bitrix24Client
from crm.providers.common.crm_credentials import CrmAccessToken
from crm.providers.common.crm_oauth_query_client import CrmOAuthQueryClient
from crm.providers.common.crm_oauth_token_store import CrmOAuthTokenStore


class Bitrix24AuthAdapter:
    def __init__(
        self,
        *,
        token_store: CrmOAuthTokenStore,
        client_id: str,
        client_secret: str,
        api_config: Bitrix24ApiConfig | None = None,
        oauth_client: CrmOAuthQueryClient | None = None,
    ) -> None:
        if not client_id.strip() or not client_secret.strip():
            raise ValueError('Bitrix24 OAuth client credentials must not be blank')
        self._store = token_store
        self._client_id = client_id.strip()
        self._client_secret = client_secret.strip()
        self._config = api_config or Bitrix24ApiConfig()
        self._oauth = oauth_client or CrmOAuthQueryClient(timeout_seconds=int(self._config.timeout_seconds))

    def exchange_code(self, *, secret_ref: str, authorization_code: str, redirect_uri: str) -> None:
        del redirect_uri
        payload = self._oauth.get_json(
            url=self._config.oauth_token_url,
            params={
                'grant_type': 'authorization_code',
                'client_id': self._client_id,
                'client_secret': self._client_secret,
                'code': authorization_code,
            },
        )
        self._save_token(secret_ref=secret_ref, payload=payload)

    def authorized_client(self, *, secret_ref: str) -> Bitrix24Client:
        token = self._store.load(provider_key='bitrix24', secret_ref=secret_ref)
        if token is None:
            raise RuntimeError('Bitrix24 OAuth token is unavailable')
        if token.is_expired():
            token = self._refresh(secret_ref=secret_ref, token=token)
        portal_base = self._config.portal_rest_base(str(token.metadata.get('client_endpoint') or ''))
        return Bitrix24Client(
            portal_rest_base=portal_base,
            access_token=token.access_token,
            timeout_seconds=self._config.timeout_seconds,
        )

    def revoke_binding(self, *, secret_ref: str) -> None:
        self._store.delete(provider_key='bitrix24', secret_ref=secret_ref)

    def _refresh(self, *, secret_ref: str, token: CrmAccessToken) -> CrmAccessToken:
        refresh_token = str(token.refresh_token or '').strip()
        if not refresh_token:
            raise RuntimeError('Bitrix24 refresh token is unavailable')
        payload = self._oauth.get_json(
            url=self._config.oauth_token_url,
            params={
                'grant_type': 'refresh_token',
                'client_id': self._client_id,
                'client_secret': self._client_secret,
                'refresh_token': refresh_token,
            },
        )
        return self._save_token(secret_ref=secret_ref, payload=payload)

    def _save_token(self, *, secret_ref: str, payload: Mapping[str, object]) -> CrmAccessToken:
        access_token = str(payload.get('access_token') or '').strip()
        refresh_token = str(payload.get('refresh_token') or '').strip()
        client_endpoint = self._config.portal_rest_base(str(payload.get('client_endpoint') or ''))
        if not access_token or not refresh_token:
            raise RuntimeError('Bitrix24 OAuth response is missing tokens')
        try:
            expires_in = int(payload.get('expires_in') or 0)
        except (TypeError, ValueError) as exc:
            raise RuntimeError('Bitrix24 OAuth expires_in is invalid') from exc
        if expires_in <= 0:
            raise RuntimeError('Bitrix24 OAuth expires_in must be positive')
        scope_raw = str(payload.get('scope') or '').replace(',', ' ')
        token = CrmAccessToken(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
            scope=tuple(part for part in scope_raw.split() if part),
            metadata={
                'client_endpoint': client_endpoint,
                'member_id': str(payload.get('member_id') or '').strip(),
            },
        )
        self._store.save(provider_key='bitrix24', secret_ref=secret_ref, token=token)
        return token

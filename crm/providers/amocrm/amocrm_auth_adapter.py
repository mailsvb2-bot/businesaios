from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone

from crm.providers.amocrm.amocrm_api_config import AmoCrmApiConfig
from crm.providers.amocrm.amocrm_client import AmoCrmClient
from crm.providers.common.crm_credentials import CrmAccessToken
from crm.providers.common.crm_http_client import CrmHttpClient, CrmHttpRequest
from crm.providers.common.crm_oauth_token_store import CrmOAuthTokenStore
from crm.providers.common.crm_retry_policy import CrmRetryPolicy


class AmoCrmAuthAdapter:
    def __init__(
        self,
        *,
        token_store: CrmOAuthTokenStore,
        client_id: str,
        client_secret: str,
        api_config: AmoCrmApiConfig | None = None,
    ) -> None:
        if not client_id.strip() or not client_secret.strip():
            raise ValueError('amoCRM OAuth client credentials must not be blank')
        self._token_store = token_store
        self._client_id = client_id.strip()
        self._client_secret = client_secret.strip()
        self._config = api_config or AmoCrmApiConfig()

    def exchange_code_with_metadata(
        self,
        *,
        secret_ref: str,
        authorization_code: str,
        redirect_uri: str,
        callback_metadata: Mapping[str, object],
    ) -> None:
        account_hint = str(callback_metadata.get('referer') or callback_metadata.get('account_url') or '').strip()
        account_base = self._config.account_base(account_hint)
        payload = self._token_request(
            account_base=account_base,
            body={
                'client_id': self._client_id,
                'client_secret': self._client_secret,
                'grant_type': 'authorization_code',
                'code': authorization_code,
                'redirect_uri': redirect_uri,
            },
        )
        self._save_token(
            secret_ref=secret_ref,
            payload=payload,
            account_base=account_base,
            redirect_uri=redirect_uri,
        )

    def authorized_client(self, *, secret_ref: str) -> AmoCrmClient:
        token = self._token_store.load(provider_key='amocrm', secret_ref=secret_ref)
        if token is None:
            raise RuntimeError('amoCRM OAuth token is unavailable')
        if token.is_expired():
            token = self._refresh(secret_ref=secret_ref, token=token)
        account_base = self._config.account_base(str(token.metadata.get('account_base_url') or ''))
        return AmoCrmClient(
            account_base_url=account_base,
            access_token=token.access_token,
            timeout_seconds=self._config.timeout_seconds,
        )

    def revoke_binding(self, *, secret_ref: str) -> None:
        self._token_store.delete(provider_key='amocrm', secret_ref=secret_ref)

    def _refresh(self, *, secret_ref: str, token: CrmAccessToken) -> CrmAccessToken:
        refresh_token = str(token.refresh_token or '').strip()
        redirect_uri = str(token.metadata.get('redirect_uri') or '').strip()
        account_base = self._config.account_base(str(token.metadata.get('account_base_url') or ''))
        if not refresh_token or not redirect_uri:
            raise RuntimeError('amoCRM refresh token metadata is incomplete')
        payload = self._token_request(
            account_base=account_base,
            body={
                'client_id': self._client_id,
                'client_secret': self._client_secret,
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
                'redirect_uri': redirect_uri,
            },
        )
        return self._save_token(
            secret_ref=secret_ref,
            payload=payload,
            account_base=account_base,
            redirect_uri=redirect_uri,
        )

    def _token_request(self, *, account_base: str, body: Mapping[str, object]) -> Mapping[str, object]:
        response = CrmHttpClient(
            base_url=account_base,
            retry_policy=CrmRetryPolicy(max_attempts=1),
        ).send(
            CrmHttpRequest(
                method='POST',
                path='/oauth2/access_token',
                json_body=dict(body),
                timeout_seconds=self._config.timeout_seconds,
            )
        )
        if not isinstance(response.json_body, Mapping):
            raise RuntimeError('amoCRM OAuth response is not a JSON object')
        return response.json_body

    def _save_token(
        self,
        *,
        secret_ref: str,
        payload: Mapping[str, object],
        account_base: str,
        redirect_uri: str,
    ) -> CrmAccessToken:
        access_token = str(payload.get('access_token') or '').strip()
        refresh_token = str(payload.get('refresh_token') or '').strip()
        if not access_token or not refresh_token:
            raise RuntimeError('amoCRM OAuth response is missing tokens')
        try:
            expires_in = int(payload.get('expires_in') or 0)
        except (TypeError, ValueError) as exc:
            raise RuntimeError('amoCRM OAuth expires_in is invalid') from exc
        if expires_in <= 0:
            raise RuntimeError('amoCRM OAuth expires_in must be positive')
        token = CrmAccessToken(
            access_token=access_token,
            token_type=str(payload.get('token_type') or 'Bearer'),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
            refresh_token=refresh_token,
            metadata={'account_base_url': account_base, 'redirect_uri': redirect_uri},
        )
        self._token_store.save(provider_key='amocrm', secret_ref=secret_ref, token=token)
        return token

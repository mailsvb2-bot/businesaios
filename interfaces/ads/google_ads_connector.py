from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, Iterable, Optional, Sequence

from interfaces.common.auth_session import AuthSession
from interfaces.common.connector_capabilities import ConnectorCapabilities
from interfaces.common.connector_maturity import ConnectorMaturity
from interfaces.common.connector_result import ConnectorResult
from interfaces.common.rate_limit_guard import RateLimitGuard
from interfaces.common.connector_support import (
    build_health,
    build_invalid_payload_result,
    build_not_configured_result,
    connector_mode,
    normalize_operation,
    normalize_payload,
)
from runtime.business_autonomy.provider_transport_bindings import provider_endpoint_url

from ._write_stage import raise_write_stage_disabled
from .base import (
    AdsConnector,
    AdsConnectorError,
    AdsPlatform,
    Campaign,
    ConnectedAccount,
    MetricPoint,
    OAuthAuthorizeURL,
)
from .oauth.authorize_builder import OAuthAuthorizeParams, build_authorize_url
from .oauth_helper import OAuthAppConfig
from .oauth_runtime_helpers import resolve_pending_account_id, resolve_runtime_oauth_value
from .oauth_state import build_state
from .ports import SecretVault
from .connector_shared import (
    http_post_compat,
    pending_account_id_from_raw,
    resolve_url_with_default,
    tokens_get_access_token_compat,
    tokens_put_compat,
)
from .connector_oauth_helpers import (
    disconnect_tokens_compat,
    resolve_oauth_client_id,
    resolve_oauth_client_secret,
    resolve_oauth_scope,
)
from .connector_exchange_support import extract_access_token, persist_connected_account
from .connector_read_specs_support import CampaignReadSpec, MetricReadSpec
from .connector_read_surface import (
    fetch_metrics_with_token,
    list_campaigns_with_token,
)
from .connector_spec_adapter_support import (
    provider_fetch_metrics_from_spec_adapter,
    provider_list_campaigns_from_spec_adapter,
)


def _google_ads_endpoint(endpoint_key: str) -> str:
    return provider_endpoint_url("google_ads", endpoint_key)


@dataclass(frozen=True)
class GoogleAdsConfig:
    """Explicit connector configuration (tests / embedded runtimes)."""

    oauth: OAuthAppConfig
    authorize_url: str = field(default_factory=lambda: _google_ads_endpoint("oauth_authorize_url"))
    token_url: str = field(default_factory=lambda: _google_ads_endpoint("oauth_token_url"))


class GoogleAdsConnector(AdsConnector):
    """Google Ads connector.

    This connector is intentionally thin: it owns OAuth + canonical mapping, while
    concrete provider I/O must be supplied by the wired HTTP/adapter object.
    That keeps the connector honest: no false-ready skeletons, but also no hidden
    business logic or parallel decision path.
    """

    _CAMPAIGN_SPEC = CampaignReadSpec(
        connector_name="GoogleAdsConnector",
        provider_method_name="google_ads_list_campaigns",
        id_keys=("id", "campaign_id", "resource_name"),
        budget_keys=("daily_budget", "daily_budget_minor"),
        name_keys=("name", "campaign_name"),
        status_keys=("status", "serving_status"),
        objective_keys=("objective", "advertising_channel_type"),
    )

    _METRIC_SPEC = MetricReadSpec(
        connector_name="GoogleAdsConnector",
        provider_method_name="google_ads_fetch_metrics",
        object_id_keys=("object_id", "campaign_id", "id"),
        day_keys=("day", "date", "segments.date"),
        spend_keys=("spend", "cost_micros"),
        spend_scale=1_000_000.0,
        conversion_keys=("conversions",),
        revenue_keys=("revenue",),
    )
    platform: AdsPlatform = AdsPlatform.GOOGLE_ADS

    def __init__(
        self,
        *,
        http: Any | None = None,
        tokens: Any | None = None,
        cfg: Optional[GoogleAdsConfig] = None,
        vault: Optional[SecretVault] = None,
    ) -> None:
        self._http = http
        self._tokens = tokens
        self._compat_session = AuthSession(configured=http is not None and tokens is not None)
        self._compat_rate_limit_guard = RateLimitGuard()
        self._cfg = cfg
        self._vault = vault

    @property
    def mode(self) -> str:
        return connector_mode(configured=self._compat_session.configured)

    def connector_maturity(self) -> ConnectorMaturity:
        return ConnectorMaturity.CAPABILITY_SHELL

    def connector_capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities(
            read=True,
            write=False,
            verify=False,
            dry_run=False,
            idempotent=False,
            metadata={"maturity": self.connector_maturity().value},
        )

    def health(self):
        capabilities = self.connector_capabilities()
        return build_health(
            connector_name="GoogleAdsConnector",
            configured=self._compat_session.configured,
            maturity=self.connector_maturity().value,
            supports_write=bool(capabilities.write),
            supports_verify=bool(capabilities.verify),
        )

    async def _http_post(
        self,
        url: str,
        *,
        headers: Dict[str, str],
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return await http_post_compat(
            self._http,
            platform=self.platform,
            url=url,
            headers=headers,
            data=data,
        )

    def _authorize_url(self, *, tenant_id: str) -> str:
        default = _google_ads_endpoint("oauth_authorize_url")
        return resolve_runtime_oauth_value(
            explicit=(self._cfg.authorize_url if self._cfg is not None else None),
            resolver=lambda: resolve_url_with_default(vault=self._vault, tenant_id=str(tenant_id or ""), vault_key=f"{self.platform.value}_authorize_url", default=default),
            default=default,
        )

    def _token_url(self, *, tenant_id: str) -> str:
        return resolve_url_with_default(
            cfg_value=self._cfg.token_url if self._cfg is not None else None,
            vault=self._vault,
            vault_key="GOOGLE_ADS_OAUTH_TOKEN_URL",
            default=_google_ads_endpoint("oauth_token_url"),
            tenant_id=str(tenant_id or ""),
        )

    def _oauth_client_id(self, *, tenant_id: str) -> str:
        _ = tenant_id
        return resolve_runtime_oauth_value(
            explicit=(self._cfg.oauth.client_id if self._cfg is not None else None),
            resolver=lambda: resolve_oauth_client_id(
                oauth=self._cfg.oauth if self._cfg is not None else None,
                vault=self._vault,
                vault_key="GOOGLE_ADS_OAUTH_CLIENT_ID",
                connector_name="GoogleAdsConnector",
                tenant_id=str(tenant_id or ""),
            ),
        )

    def _oauth_client_secret(self, *, tenant_id: str) -> str:
        _ = tenant_id
        return resolve_runtime_oauth_value(
            explicit=(self._cfg.oauth.client_secret if self._cfg is not None else None),
            resolver=lambda: resolve_oauth_client_secret(
                oauth=self._cfg.oauth if self._cfg is not None else None,
                vault=self._vault,
                vault_key="GOOGLE_ADS_OAUTH_CLIENT_SECRET",
                connector_name="GoogleAdsConnector",
                tenant_id=str(tenant_id or ""),
            ),
        )

    def _pending_account_id(self, *, tenant_id: str, raw: Dict[str, Any]) -> str:
        return resolve_pending_account_id(
            tenant_id=tenant_id,
            raw=raw,
            extractor=lambda tid, payload: pending_account_id_from_raw(
                tenant_id=tid,
                raw=payload,
                candidate_keys=("customer_id", "customer_ids", "advertiser_id", "advertiser_ids", "account_id", "account_ids"),
                pending_prefix="google_ads_oauth_pending_selection",
            ),
        )

    def _oauth_scope(self, *, tenant_id: str) -> str:
        return resolve_oauth_scope(
            oauth=self._cfg.oauth if self._cfg is not None else None,
            vault=self._vault,
            vault_key="GOOGLE_ADS_OAUTH_SCOPES",
            tenant_id=str(tenant_id or ""),
            default=_google_ads_endpoint("oauth_scope"),
        )

    async def _tokens_put(
        self,
        *,
        tenant_id: str,
        account_id: str,
        access_token: str,
        scope: str,
    ) -> None:
        await tokens_put_compat(
            tokens=self._tokens,
            tenant_id=tenant_id,
            platform=self.platform,
            account_id=account_id,
            access_token=access_token,
            scope=scope,
            connector_name="GoogleAdsConnector",
        )

    async def _tokens_get_access_token(self, *, tenant_id: str, account_id: str) -> str:
        return await tokens_get_access_token_compat(
            tokens=self._tokens,
            tenant_id=tenant_id,
            platform=self.platform,
            account_id=account_id,
        )

    def execute(self, operation: str, payload: Dict[str, Any], *, idempotency_key: str | None = None, dry_run: bool = False) -> ConnectorResult:
        if hasattr(self, 'decide'):
            raise RuntimeError('connectors must never expose decide()')
        op = normalize_operation(operation)
        if not op:
            return ConnectorResult(ok=False, code='invalid_operation', message='operation is required')
        normalized_payload = normalize_payload(payload)
        if normalized_payload is None:
            return build_invalid_payload_result(connector_name='GoogleAdsConnector', operation=op)
        if not self._compat_rate_limit_guard.allow(f'google_ads:{op}'):
            return ConnectorResult(ok=False, code='rate_limited', message='connector rate limit reached')
        if not self._compat_session.configured:
            return build_not_configured_result(connector_name='GoogleAdsConnector', operation=op)
        return ConnectorResult(ok=False, code='async_only', message='use async AdsReadConnector/AdsWriteConnector methods', payload={'operation': op, 'mode': self.mode, 'maturity': self.connector_maturity().value, 'capabilities': self.connector_capabilities().as_dict()})

    async def connect(self, *, tenant_id: str, redirect_uri: str) -> OAuthAuthorizeURL:
        state = build_state(tenant_id=tenant_id)
        return build_authorize_url(
            OAuthAuthorizeParams(
                base_url=self._authorize_url(tenant_id=tenant_id),
                client_id=self._oauth_client_id(tenant_id=tenant_id),
                redirect_uri=redirect_uri,
                scope=self._oauth_scope(tenant_id=tenant_id),
                state=state,
                extra={"access_type": "offline", "prompt": "consent"},
            )
        )

    async def exchange_code(
        self,
        *,
        tenant_id: str,
        code: str,
        redirect_uri: str,
    ) -> ConnectedAccount:
        if not code:
            raise AdsConnectorError("Google OAuth exchange: missing code")

        raw = await self._http_post(
            self._token_url(tenant_id=tenant_id),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self._oauth_client_id(tenant_id=tenant_id),
                "client_secret": self._oauth_client_secret(tenant_id=tenant_id),
                "redirect_uri": redirect_uri,
            },
        )

        access_token = extract_access_token(
            raw=raw,
            candidate_keys=("access_token",),
            connector_name="Google OAuth exchange",
        )
        account_id = self._pending_account_id(tenant_id=tenant_id, raw=raw)
        return await persist_connected_account(
            platform=self.platform,
            tenant_id=tenant_id,
            account_id=account_id,
            access_token=access_token,
            scope=self._oauth_scope(tenant_id=tenant_id),
            display_name="Google Ads",
            tokens_put=self._tokens_put,
        )

    async def disconnect(self, *, tenant_id: str, account_id: str) -> None:
        await disconnect_tokens_compat(
            tokens=self._tokens,
            tenant_id=tenant_id,
            platform=self.platform,
            account_id=account_id,
            connector_name="GoogleAdsConnector",
        )

    async def _provider_list_campaigns(
        self,
        *,
        tenant_id: str,
        account_id: str,
        access_token: str,
    ) -> Sequence[dict[str, Any]]:
        return await provider_list_campaigns_from_spec_adapter(
            http=self._http,
            platform=self.platform,
            tenant_id=tenant_id,
            account_id=account_id,
            access_token=access_token,
            spec=self._CAMPAIGN_SPEC,
        )

    async def _provider_fetch_metrics(
        self,
        *,
        tenant_id: str,
        account_id: str,
        access_token: str,
        level: str,
        object_ids: Optional[Sequence[str]],
        date_from: date,
        date_to: date,
    ) -> Iterable[dict[str, Any]]:
        return await provider_fetch_metrics_from_spec_adapter(
            http=self._http,
            platform=self.platform,
            tenant_id=tenant_id,
            account_id=account_id,
            access_token=access_token,
            level=level,
            object_ids=object_ids,
            date_from=date_from,
            date_to=date_to,
            spec=self._METRIC_SPEC,
        )

    def _campaign_from_row(self, *, account_id: str, row: Dict[str, Any]) -> Campaign:
        from .connector_spec_adapter_support import campaign_from_spec_adapter

        return campaign_from_spec_adapter(
            platform=self.platform,
            account_id=account_id,
            row=row,
            spec=self._CAMPAIGN_SPEC,
        )

    def _metric_from_row(
        self,
        *,
        account_id: str,
        level: str,
        row: Dict[str, Any],
    ) -> MetricPoint:
        from .connector_spec_adapter_support import metric_from_spec_adapter

        return metric_from_spec_adapter(
            platform=self.platform,
            account_id=account_id,
            level=level,
            row=row,
            spec=self._METRIC_SPEC,
        )

    async def list_campaigns(self, *, tenant_id: str, account_id: str) -> Sequence[Campaign]:
        return await list_campaigns_with_token(
            tenant_id=tenant_id,
            account_id=account_id,
            get_access_token=self._tokens_get_access_token,
            provider_list_campaigns=self._provider_list_campaigns,
            campaign_mapper=self._campaign_from_row,
        )

    async def fetch_metrics(
        self,
        *,
        tenant_id: str,
        account_id: str,
        level: str,
        object_ids: Optional[Sequence[str]],
        date_from: date,
        date_to: date,
    ) -> Iterable[MetricPoint]:
        return await fetch_metrics_with_token(
            tenant_id=tenant_id,
            account_id=account_id,
            level=level,
            object_ids=object_ids,
            date_from=date_from,
            date_to=date_to,
            get_access_token=self._tokens_get_access_token,
            provider_fetch_metrics=self._provider_fetch_metrics,
            metric_mapper=self._metric_from_row,
        )

    async def create_or_update(
        self,
        *,
        tenant_id: str,
        account_id: str,
        object_type: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        raise_write_stage_disabled(
            connector_name='GoogleAdsConnector',
            provider='google_ads',
            operation=f"create_or_update:{object_type}",
            payload=payload,
        )


__all__ = ["GoogleAdsConfig", "GoogleAdsConnector"]

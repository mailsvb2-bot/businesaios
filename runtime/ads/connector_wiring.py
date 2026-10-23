"""Wave 6: wire Yandex Direct into AdsConnectorRegistry (port of ClientPlatform ad_connections).

Reuses existing owners only: oauth_state/authorize_builder/YandexOAuthExchanger for the
connection, the async TokenStore port for tokens, GovernedYandexDirectConnector for
governed publication (create + independent readback). Opt-in: BUSINESAIOS_AD_CONNECTIONS=1.
Client secret comes from a SecretVault reference, never from config text.
"""

from __future__ import annotations

import os
import time
from collections.abc import Mapping
from typing import Any

from interfaces.ads.base import AdsPlatform
from interfaces.ads.oauth.authorize_builder import OAuthAuthorizeParams, build_authorize_url
from interfaces.ads.oauth_exchange import OAuthClientConfig, YandexOAuthExchanger
from interfaces.ads.oauth_state import build_state, parse_state
from interfaces.ads.registry import AdsConnectorRegistry
from interfaces.ads.yandex_direct_governed_execution import DirectPublicationBinding, GovernedYandexDirectConnector

CANON_ADS_CONNECTOR_WIRING = True
YANDEX_AUTHORIZE_URL = "https://oauth.yandex.ru/authorize"
YANDEX_TOKEN_URL = "https://oauth.yandex.ru/token"
STATE_MAX_AGE_SEC = 900


def ad_connections_enabled(env: Mapping[str, str] | None = None) -> bool:
    return str((env or os.environ).get("BUSINESAIOS_AD_CONNECTIONS", "0")).strip().lower() in {"1", "true", "yes"}


def yandex_direct_configured(env: Mapping[str, str] | None = None) -> bool:
    e = env or os.environ
    return bool(e.get("YANDEX_DIRECT_CLIENT_ID") and e.get("YANDEX_DIRECT_CLIENT_SECRET_REF"))


def start_yandex_direct_oauth(*, tenant_id: str, redirect_uri: str, env: Mapping[str, str] | None = None) -> str:
    e = env or os.environ
    if not ad_connections_enabled(e) or not yandex_direct_configured(e):
        raise PermissionError("ad_connections_disabled")
    params = OAuthAuthorizeParams(
        base_url=YANDEX_AUTHORIZE_URL,
        client_id=e["YANDEX_DIRECT_CLIENT_ID"],
        redirect_uri=redirect_uri,
        scope="direct:api",
        state=build_state(tenant_id=tenant_id),
    )
    return build_authorize_url(params).url


async def complete_yandex_direct_oauth(
    *,
    tenant_id: str,
    state: str,
    code: str,
    redirect_uri: str,
    account_id: str,
    http: Any,
    vault: Any,
    token_store: Any,
    env: Mapping[str, str] | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Validate state (tenant + age), exchange the code, store the token; returns no token material."""
    e = env or os.environ
    parsed = parse_state(state)
    age = (now or time.time()) - (parsed.issued_at_ts if parsed else 0)
    if parsed is None or parsed.tenant_id != tenant_id or not 0 <= age <= STATE_MAX_AGE_SEC:
        raise PermissionError("oauth_state_invalid")
    cfg = OAuthClientConfig(
        token_url=YANDEX_TOKEN_URL,
        client_id=e["YANDEX_DIRECT_CLIENT_ID"],
        client_secret=vault.get_secret(e["YANDEX_DIRECT_CLIENT_SECRET_REF"]),
    )
    result = await YandexOAuthExchanger(http=http, cfg=cfg).exchange(code=code, redirect_uri=redirect_uri)
    token = {
        "access_token": result.access_token,
        "refresh_token": result.refresh_token,
        "expires_in": result.expires_in,
    }
    await token_store.put(tenant_id=tenant_id, platform=AdsPlatform.YANDEX_DIRECT, account_id=account_id, token=token)
    return {"platform": "yandex_direct", "account_id": account_id, "connected": True}


async def disconnect_ad_connection(*, tenant_id: str, account_id: str, token_store: Any) -> None:
    await token_store.delete(tenant_id=tenant_id, platform=AdsPlatform.YANDEX_DIRECT, account_id=account_id)


def build_ads_connector_registry(
    *,
    binding: DirectPublicationBinding | None,
    send: Any = None,
    read: Any = None,
    env: Mapping[str, str] | None = None,
) -> AdsConnectorRegistry:
    """Registry for one governed publication; empty when disabled or unbound (fail-closed)."""
    registry: AdsConnectorRegistry = AdsConnectorRegistry()
    if ad_connections_enabled(env) and binding is not None:
        registry.register(GovernedYandexDirectConnector(binding=binding, send=send, read=read))
    return registry


def list_ad_connections(registry: AdsConnectorRegistry) -> list[dict[str, object]]:
    return [dict(row) for row in registry.snapshot()]

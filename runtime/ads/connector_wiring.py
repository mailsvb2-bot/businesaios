"""Wave 6: wire Yandex Direct into AdsConnectorRegistry (port of ClientPlatform ad_connections).

Reuses existing owners only: oauth_state/authorize_builder/YandexOAuthExchanger for the
connection and the async TokenStore port for tokens. Governed publication stays with
bootstrap.ads_write_gateway + GovernedYandexDirectConnector. Opt-in: BUSINESAIOS_AD_CONNECTIONS=1.
Client secret comes from a SecretVault reference, never from config text.
"""

from __future__ import annotations

import hashlib
import os
import time
from collections.abc import Mapping
from typing import Any

from interfaces.ads.base import AdsPlatform
from interfaces.ads.oauth.authorize_builder import OAuthAuthorizeParams, build_authorize_url
from interfaces.ads.oauth_exchange import OAuthClientConfig, YandexOAuthExchanger
from interfaces.ads.oauth_state import build_state, parse_state
from interfaces.ads.registry import CONNECTORS

CANON_ADS_CONNECTOR_WIRING = True
YANDEX_AUTHORIZE_URL = "https://oauth.yandex.ru/authorize"
YANDEX_TOKEN_URL = "https://oauth.yandex.ru/token"
STATE_MAX_AGE_SEC = 900
REUSABLE_OAUTH_CODE_ERRORS = frozenset({"provider_invalid_grant", "provider_bad_verification_code"})


def oauth_state_digest(state: str) -> str:
    """Only the digest of an OAuth state is ever persisted, never the state itself."""
    return hashlib.sha256(str(state).encode()).hexdigest()


class InMemoryOAuthStateStore:
    """Single-use bookkeeping for stateless OAuth states (reserve -> consume | release).

    In-process reference/fake implementation of the store port; production wiring injects a durable one.
    """

    def __init__(self) -> None:
        self.consumed: dict[str, str] = {}
        self.reserved: set[str] = set()

    def reserve(self, digest: str) -> bool:
        if digest in self.consumed or digest in self.reserved:
            return False
        self.reserved.add(digest)
        return True

    def release(self, digest: str) -> None:
        self.reserved.discard(digest)

    def consume(self, digest: str, reason: str = "completed") -> bool:
        self.reserved.discard(digest)
        if digest in self.consumed:
            return False
        self.consumed[digest] = reason
        return True


def _checked_state(tenant_id: str, state: str, now: float | None) -> None:
    parsed = parse_state(state)
    age = (now or time.time()) - (parsed.issued_at_ts if parsed else 0)
    if parsed is None or parsed.tenant_id != tenant_id or not 0 <= age <= STATE_MAX_AGE_SEC:
        raise PermissionError("oauth_state_invalid")


def cancel_yandex_direct_oauth(*, tenant_id: str, state: str, oauth_store: Any, now: float | None = None) -> bool:
    """Consume an outstanding OAuth state without contacting the provider (donor cancel). True = newly cancelled."""
    _checked_state(tenant_id, state, now)
    return bool(oauth_store.consume(oauth_state_digest(state), "cancelled"))


def settle_failed_oauth_completion(*, oauth_store: Any, digest: str, reusable: bool) -> None:
    """After a failed code exchange: a provider-reported reusable error releases the state, anything else burns it."""
    if reusable:
        oauth_store.release(digest)
    else:
        oauth_store.consume(digest, "failed")


def per_connection_readiness_enabled(env: Mapping[str, str] | None = None) -> bool:
    return str((env or os.environ).get("BAI_ADS_PER_CONNECTION_READINESS_ENABLED", "0")).lower() in {
        "1", "true", "yes"
    }


def direct_connection_key(*, business_id: str, account_id: str) -> str:
    for label, value in (("business", business_id), ("account", account_id)):
        if (not isinstance(value, str) or not value.strip() or value != value.strip()
                or "::" in value or len(value) > 160):
            raise ValueError(f"direct_connection_{label}_invalid")
    return f"{business_id}::{account_id}"


def _token_key(*, business_id: str | None, account_id: str) -> str:
    if per_connection_readiness_enabled():
        if not business_id:
            raise PermissionError("direct_connection_business_scope_required")
        return direct_connection_key(business_id=business_id, account_id=account_id)
    return account_id


DIRECT_LIVE_CAMPAIGN_STATES = frozenset({"ON", "OFF", "SUSPENDED"})


def prepare_direct_rights_requests(*, campaign_id: int, ad_group_id: int):
    """Official read-only Direct v5 get envelopes; no writes or made-up identifiers."""
    for label, identifier in (("campaign_id", campaign_id), ("ad_group_id", ad_group_id)):
        if type(identifier) is not int or not 0 < identifier < 2**63:
            raise ValueError(f"direct_{label}_invalid")
    return (
        ("clients", {"method": "get", "params": {"FieldNames": ["Login", "Grants"]}}),
        ("campaigns", {"method": "get", "params": {"SelectionCriteria": {"Ids": [campaign_id]},
                                                  "FieldNames": ["Id", "State", "Status"]}}),
        ("adgroups", {"method": "get", "params": {"SelectionCriteria": {"Ids": [ad_group_id]},
                                                 "FieldNames": ["Id", "CampaignId", "Status"]}}),
    )


def _required_direct_row(response: object, key: str):
    if not isinstance(response, Mapping) or response.get("error") is not None:
        raise ValueError("direct_provider_read_failed")
    result = response.get("result")
    rows = result.get(key) if isinstance(result, Mapping) else None
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], Mapping):
        raise ValueError("direct_provider_read_ambiguous")
    return rows[0]


async def direct_connection_readiness(
    *, tenant_id: str, business_id: str, account_id: str,
    campaign_id: int, ad_group_id: int, token_store: Any, read: Any, writes_enabled: bool,
) -> dict[str, Any]:
    """Prove one scoped connection, grants and campaign ownership via sealed reads."""
    key = direct_connection_key(business_id=business_id, account_id=account_id)
    token = await token_store.get(
        tenant_id=tenant_id, platform=AdsPlatform.YANDEX_DIRECT, account_id=key,
    )
    checks = [("business_bound_token", bool(token))]
    if token:
        try:
            received = {}
            for endpoint, request in prepare_direct_rights_requests(
                campaign_id=campaign_id, ad_group_id=ad_group_id,
            ):
                received[endpoint] = await read(account_id=account_id, service=endpoint, request=request)
            rights = _required_direct_row(received["clients"], "Clients").get("Grants")
            checks.append(("edit_campaigns_grant", isinstance(rights, list) and any(
                isinstance(item, Mapping) and item.get("Privilege") == "EDIT_CAMPAIGNS"
                and item.get("Value") == "YES" for item in rights
            )))
            campaign = _required_direct_row(received["campaigns"], "Campaigns")
            checks.append(("campaign_live", campaign.get("Id") == campaign_id
                           and campaign.get("State") in DIRECT_LIVE_CAMPAIGN_STATES
                           and campaign.get("Status") != "REJECTED"))
            group = _required_direct_row(received["adgroups"], "AdGroups")
            checks.append(("ad_group_in_campaign", group.get("Id") == ad_group_id
                           and group.get("CampaignId") == campaign_id))
        except Exception:
            checks.append(("readback_unverified", False))
    truth = CONNECTORS["yandex_direct"]
    checks.append(("execution_capability", bool(
        truth["implemented"] and truth["write"] and truth["verify"] and writes_enabled
    )))
    failed = [name for name, passed in checks if not passed]
    return {"ready": not failed, "reason": failed[0] if failed else "",
            "scope": {"tenant_id": tenant_id, "business_id": business_id, "account_id": account_id},
            "checks": [{"check": name, "passed": bool(passed)} for name, passed in checks],
            "campaign_id": campaign_id, "ad_group_id": ad_group_id,
            "global_production_ready": bool(truth["production_ready"])}


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
    oauth_store: Any = None,
    business_id: str | None = None,
) -> dict[str, Any]:
    """Validate state (tenant + age), exchange the code, store the token; returns no token material.

    With ``oauth_store`` the state is single-use: a cancelled/used state is rejected and a failed exchange
    releases (reusable provider error) or burns the state.
    """
    e = env or os.environ
    _checked_state(tenant_id, state, now)
    token_key = _token_key(business_id=business_id, account_id=account_id)
    digest = oauth_state_digest(state)
    if oauth_store is not None and not oauth_store.reserve(digest):
        raise PermissionError("oauth_state_consumed")
    try:
        cfg = OAuthClientConfig(
            token_url=YANDEX_TOKEN_URL,
            client_id=e["YANDEX_DIRECT_CLIENT_ID"],
            client_secret=vault.get_secret(e["YANDEX_DIRECT_CLIENT_SECRET_REF"]),
        )
        result = await YandexOAuthExchanger(http=http, cfg=cfg).exchange(code=code, redirect_uri=redirect_uri)
    except Exception as exc:
        if oauth_store is not None:
            settle_failed_oauth_completion(
                oauth_store=oauth_store, digest=digest, reusable=getattr(exc, "code", "") in REUSABLE_OAUTH_CODE_ERRORS
            )
        raise
    token = {
        "access_token": result.access_token,
        "refresh_token": result.refresh_token,
        "expires_in": result.expires_in,
    }
    await token_store.put(tenant_id=tenant_id, platform=AdsPlatform.YANDEX_DIRECT,
                          account_id=token_key, token=token)
    if oauth_store is not None:
        oauth_store.consume(digest, "completed")
    result = {"platform": "yandex_direct", "account_id": account_id, "connected": True}
    return {**result, "business_id": business_id} if token_key != account_id else result


async def disconnect_ad_connection(*, tenant_id: str, account_id: str, token_store: Any,
                                   business_id: str | None = None) -> None:
    await token_store.delete(tenant_id=tenant_id, platform=AdsPlatform.YANDEX_DIRECT,
                             account_id=_token_key(business_id=business_id, account_id=account_id))


async def list_ad_connections(*, tenant_id: str, account_ids: list[str], token_store: Any,
                              business_id: str | None = None) -> list[dict[str, object]]:
    """Connection status from registry truth + token presence; never returns token material.

    Registry ownership stays in bootstrap/ads_wiring.py; a governed Yandex Direct
    connector is bound per reviewed publication (DirectPublicationBinding).
    """
    truth = CONNECTORS["yandex_direct"]
    rows: list[dict[str, object]] = []
    for account_id in account_ids:
        token = await token_store.get(tenant_id=tenant_id, platform=AdsPlatform.YANDEX_DIRECT,
                                      account_id=_token_key(business_id=business_id, account_id=account_id))
        rows.append(
            {
                "platform": "yandex_direct",
                "account_id": account_id,
                "connected": bool(token),
                "production_ready": bool(truth["production_ready"]),
                "requires_human_approval": bool(truth["requires_human_approval"]),
            }
        )
    return rows

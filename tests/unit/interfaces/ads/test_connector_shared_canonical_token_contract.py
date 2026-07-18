from __future__ import annotations

import asyncio

from interfaces.ads.base import AdsPlatform
from interfaces.ads.connector_shared import (
    tokens_get_access_token_compat,
    tokens_put_compat,
)


def _run(coro):
    return asyncio.run(coro)


def test_canonical_token_store_receives_ads_platform_enum():
    seen = []

    class Store:
        async def put(self, *, tenant_id, platform, account_id, token):
            seen.append((tenant_id, platform, account_id, token))

        async def get(self, *, tenant_id, platform, account_id):
            seen.append((tenant_id, platform, account_id))
            return {"access_token": "token"}

    store = Store()
    _run(
        tokens_put_compat(
            tokens=store,
            tenant_id="tenant-a",
            platform=AdsPlatform.GOOGLE_ADS,
            account_id="account-a",
            access_token="token",
            scope="scope-a",
            connector_name="GoogleAdsConnector",
        )
    )
    assert _run(
        tokens_get_access_token_compat(
            tokens=store,
            tenant_id="tenant-a",
            platform=AdsPlatform.GOOGLE_ADS,
            account_id="account-a",
        )
    ) == "token"
    assert seen[0][1] is AdsPlatform.GOOGLE_ADS
    assert seen[1][1] is AdsPlatform.GOOGLE_ADS


def test_legacy_token_store_receives_platform_value_string():
    seen = []

    class Store:
        def put_token(self, tenant_id, platform, account_id, access_token, scope):
            seen.append((tenant_id, platform, account_id, access_token, scope))

        def get_access_token(self, tenant_id, platform, account_id):
            seen.append((tenant_id, platform, account_id))
            return "token"

    store = Store()
    _run(
        tokens_put_compat(
            tokens=store,
            tenant_id="tenant-a",
            platform=AdsPlatform.GOOGLE_ADS,
            account_id="account-a",
            access_token="token",
            scope="scope-a",
            connector_name="GoogleAdsConnector",
        )
    )
    assert _run(
        tokens_get_access_token_compat(
            tokens=store,
            tenant_id="tenant-a",
            platform=AdsPlatform.GOOGLE_ADS,
            account_id="account-a",
        )
    ) == "token"
    assert seen[0][1] == "google_ads"
    assert seen[1][1] == "google_ads"

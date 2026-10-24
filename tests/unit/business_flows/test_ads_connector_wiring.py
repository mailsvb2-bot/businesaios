import asyncio
import time

import pytest

from interfaces.ads.registry import CONNECTORS
from interfaces.ads.yandex_direct_governed_execution import GovernedYandexDirectConnector
from runtime.ads import connector_wiring as w
from tests.integration.ads.test_phase18_governed_yandex_execution_journey import bound

ENV = {
    "BUSINESAIOS_AD_CONNECTIONS": "1",
    "YANDEX_DIRECT_CLIENT_ID": "cid",
    "YANDEX_DIRECT_CLIENT_SECRET_REF": "vault:yd",
}


class Http:
    def __init__(self):
        self.posts = []

    async def post(self, url, *, headers, data=None):
        self.posts.append((url, data))
        return {"access_token": "AT", "refresh_token": "RT", "expires_in": 3600}


class Vault:
    def get_secret(self, key):
        assert key == "vault:yd"
        return "secret"


class Store:
    def __init__(self):
        self.items = {}

    async def put(self, *, tenant_id, platform, account_id, token):
        self.items[(tenant_id, platform.value, account_id)] = token

    async def delete(self, *, tenant_id, platform, account_id):
        self.items.pop((tenant_id, platform.value, account_id), None)


def test_oauth_disabled_by_default():
    with pytest.raises(PermissionError):
        w.start_yandex_direct_oauth(tenant_id="t1", redirect_uri="https://x/cb", env={})


def test_oauth_roundtrip_stores_token_and_returns_no_secret():
    url = w.start_yandex_direct_oauth(tenant_id="t1", redirect_uri="https://x/cb", env=ENV)
    assert url.startswith(w.YANDEX_AUTHORIZE_URL) and "client_id=cid" in url
    state = url.split("state=")[1].split("&")[0].replace("%3A", ":")
    http, store = Http(), Store()
    kw = dict(
        code="c", redirect_uri="https://x/cb", account_id="acc", http=http, vault=Vault(), token_store=store, env=ENV
    )
    out = asyncio.run(w.complete_yandex_direct_oauth(tenant_id="t1", state=state, **kw))
    assert out == {"platform": "yandex_direct", "account_id": "acc", "connected": True}
    assert store.items[("t1", "yandex_direct", "acc")]["access_token"] == "AT"
    assert http.posts[0][1]["client_secret"] == "secret"
    with pytest.raises(PermissionError):
        asyncio.run(w.complete_yandex_direct_oauth(tenant_id="t2", state=state, **kw))
    with pytest.raises(PermissionError):
        asyncio.run(w.complete_yandex_direct_oauth(tenant_id="t1", state=state, now=time.time() + 3600, **kw))
    asyncio.run(w.disconnect_ad_connection(tenant_id="t1", account_id="acc", token_store=store))
    assert store.items == {}


def test_list_connections_and_registry_registration():
    from interfaces.ads.registry import AdsConnectorRegistry

    store = Store()
    store.items[("t1", "yandex_direct", "a1")] = {"access_token": "AT"}

    async def get(*, tenant_id, platform, account_id):
        return store.items.get((tenant_id, platform.value, account_id))

    store.get = get
    rows = asyncio.run(w.list_ad_connections(tenant_id="t1", account_ids=["a1", "a2"], token_store=store))
    assert [r["connected"] for r in rows] == [True, False]
    assert "AT" not in repr(rows) and rows[0]["production_ready"] is False

    async def t(**_):
        return {}

    reg = AdsConnectorRegistry()
    reg.register(GovernedYandexDirectConnector(binding=bound(), send=t, read=t))
    assert reg.has("yandex_direct")
    # Real writes stay blocked by the canonical gateway until production readiness is proven.
    assert CONNECTORS["yandex_direct"]["production_ready"] is False


def _state():
    url = w.start_yandex_direct_oauth(tenant_id="t1", redirect_uri="https://x/cb", env=ENV)
    return url.split("state=")[1].split("&")[0].replace("%3A", ":")


def _complete(state, http, store, oauth_store, tenant="t1"):
    return asyncio.run(
        w.complete_yandex_direct_oauth(
            tenant_id=tenant, state=state, code="c", redirect_uri="https://x/cb", account_id="acc",
            http=http, vault=Vault(), token_store=store, env=ENV, oauth_store=oauth_store,
        )
    )


def test_cancelled_state_is_single_use_and_never_reaches_provider():
    state, ost, http, store = _state(), w.InMemoryOAuthStateStore(), Http(), Store()
    assert w.cancel_yandex_direct_oauth(tenant_id="t1", state=state, oauth_store=ost) is True
    assert w.cancel_yandex_direct_oauth(tenant_id="t1", state=state, oauth_store=ost) is False
    with pytest.raises(PermissionError, match="oauth_state_consumed"):
        _complete(state, http, store, ost)
    assert http.posts == [] and store.items == {}
    with pytest.raises(PermissionError, match="oauth_state_invalid"):  # foreign tenant cannot cancel
        w.cancel_yandex_direct_oauth(tenant_id="t2", state=state, oauth_store=ost)
    assert state not in str(ost.consumed)  # only digests are kept


def test_completion_consumes_state_and_failed_exchange_settles_it():
    ost, http, store = w.InMemoryOAuthStateStore(), Http(), Store()
    s1 = _state()
    assert _complete(s1, http, store, ost)["connected"] is True
    with pytest.raises(PermissionError, match="oauth_state_consumed"):  # replay of a used callback
        _complete(s1, http, store, ost)

    class Boom(Http):
        def __init__(self, code):
            super().__init__()
            self.code = code

        async def post(self, url, *, headers, data=None):
            err = RuntimeError("x")
            err.code = self.code
            raise err

    s2, s3 = _state(), _state()
    time.sleep(0)  # states carry their own issue time; distinct tenants/time are not required for digests
    ost2 = w.InMemoryOAuthStateStore()
    with pytest.raises(RuntimeError):
        _complete(s2, Boom("provider_invalid_grant"), store, ost2)
    assert ost2.reserved == set() and ost2.consumed == {}  # reusable: released, can be retried
    with pytest.raises(RuntimeError):
        _complete(s3, Boom("provider_500"), store, ost2)
    assert list(ost2.consumed.values()) == ["failed"]  # anything else burns the state

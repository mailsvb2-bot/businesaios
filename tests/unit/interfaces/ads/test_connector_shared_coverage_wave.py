from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from interfaces.ads import connector_shared as shared
from interfaces.ads.base import AdsConnectorError, AdsPlatform


def run(coro):
    return asyncio.run(coro)


def test_secret_mapping_and_stable_payload_contracts():
    assert shared._normalize_secret_value(None) is None
    assert shared._normalize_secret_value("   ") is None
    assert shared._normalize_secret_value(7) == "7"
    assert shared._normalized_mapping({"ok": 1}) == {"ok": 1}
    with pytest.raises(AdsConnectorError, match="mapping payload"):
        shared._normalized_mapping([("ok", 1)])

    left = {"b": (2, 1), "a": {"mixed": {1, "1"}}}
    right = {"a": {"mixed": {"1", 1}}, "b": [2, 1]}
    assert shared.stable_payload_hash(left) == shared.stable_payload_hash(right)
    with pytest.raises(AdsConnectorError, match="duplicate normalized key"):
        shared.stable_payload_hash({1: "numeric", "1": "string"})


def test_maybe_await_and_compat_invocation_do_not_mask_internal_type_errors():
    async def async_value():
        return "async"

    assert run(shared._maybe_await("sync")) == "sync"
    assert run(shared._maybe_await(async_value())) == "async"

    def keyword_only(*, value):
        return value

    assert shared._call_sync_compat(
        keyword_only,
        [(("bad",), {}), ((), {"value": "ok"})],
    ) == "ok"

    calls = []

    def raises_inside(*, value):
        calls.append(value)
        raise TypeError("business failure")

    with pytest.raises(TypeError, match="business failure"):
        shared._call_sync_compat(
            raises_inside,
            [((), {"value": "once"}), (("fallback",), {})],
        )
    assert calls == ["once"]

    with pytest.raises(shared._NoCompatibleCall):
        shared._call_sync_compat(keyword_only, [(("x",), {})])


def test_vault_compatibility_and_pending_account_resolution():
    assert shared.vault_get_secret(None, tenant_id="t", key="k") is None
    assert shared.vault_get_secret(object(), tenant_id="t", key="k") is None

    class TenantVault:
        def get_secret(self, tenant_id, key):
            assert tenant_id == "tenant-a"
            assert key == "secret"
            return " tenant-value "

    assert shared.vault_get_secret(
        TenantVault(), tenant_id="tenant-a", key="secret"
    ) == "tenant-value"

    class TenantMissingVault:
        def get_secret(self, tenant_id, key):
            return None

    assert shared.vault_get_secret(
        TenantMissingVault(), tenant_id="tenant-a", key="secret"
    ) is None

    class GlobalVault:
        def get_secret(self, key):
            return " global-value " if key == "secret" else None

    assert shared.vault_get_secret(
        GlobalVault(), tenant_id="tenant-a", key="secret"
    ) == "global-value"

    class BrokenVault:
        def get_secret(self, key):
            raise TypeError("vault backend failed")

    with pytest.raises(TypeError, match="vault backend failed"):
        shared.vault_get_secret(BrokenVault(), tenant_id=None, key="secret")

    keys = ("account_id", "customer_id")
    assert shared.pending_account_id_from_raw(
        tenant_id="tenant-a",
        raw={"account_id": 0},
        candidate_keys=keys,
        pending_prefix="pending",
    ) == "0"
    assert shared.pending_account_id_from_raw(
        tenant_id="tenant-a",
        raw={"data": {"customer_id": {"id": " nested "}}},
        candidate_keys=keys,
        pending_prefix="pending",
    ) == "nested"
    assert shared.pending_account_id_from_raw(
        tenant_id=" ",
        raw={"account_id": ["one", "two"]},
        candidate_keys=keys,
        pending_prefix=" pending ",
    ) == "pending:default"

    assert shared._first_scalar({"advertiser_id": " adv "}) == "adv"
    assert shared._first_scalar({"other": "x"}) == ""
    assert shared._first_scalar([" only "]) == "only"
    assert shared._first_scalar({"a", "b"}) == ""
    assert shared._first_scalar(None) == ""


def test_token_put_supports_canonical_and_legacy_stores():
    with pytest.raises(AdsConnectorError, match="not configured"):
        run(
            shared.tokens_put_compat(
                tokens=None,
                tenant_id="t",
                platform=AdsPlatform.GOOGLE_ADS,
                account_id="a",
                access_token="token",
                scope="scope",
                connector_name="GoogleAdsConnector",
            )
        )

    canonical_calls = []

    class CanonicalStore:
        async def put(self, *, tenant_id, platform, account_id, token):
            canonical_calls.append((tenant_id, platform, account_id, token))

    run(
        shared.tokens_put_compat(
            tokens=CanonicalStore(),
            tenant_id="t",
            platform=AdsPlatform.GOOGLE_ADS,
            account_id="a",
            access_token="token",
            scope="scope",
            connector_name="GoogleAdsConnector",
        )
    )
    assert canonical_calls == [
        ("t", "google_ads", "a", {"access_token": "token", "scope": "scope"})
    ]

    legacy_calls = []

    class LegacyStore:
        def put_token(self, tenant_id, platform, account_id, access_token, scope):
            legacy_calls.append((tenant_id, platform, account_id, access_token, scope))

    run(
        shared.tokens_put_compat(
            tokens=LegacyStore(),
            tenant_id="t",
            platform=AdsPlatform.GOOGLE_ADS,
            account_id="a",
            access_token="token",
            scope="scope",
            connector_name="GoogleAdsConnector",
        )
    )
    assert legacy_calls == [("t", "google_ads", "a", "token", "scope")]

    internal_calls = []

    class BrokenStore:
        def put_token(self, **payload):
            internal_calls.append(payload)
            raise TypeError("storage transaction failed")

    with pytest.raises(TypeError, match="storage transaction failed"):
        run(
            shared.tokens_put_compat(
                tokens=BrokenStore(),
                tenant_id="t",
                platform=AdsPlatform.GOOGLE_ADS,
                account_id="a",
                access_token="token",
                scope="scope",
                connector_name="GoogleAdsConnector",
            )
        )
    assert len(internal_calls) == 1

    with pytest.raises(AdsConnectorError, match="must expose"):
        run(
            shared.tokens_put_compat(
                tokens=SimpleNamespace(put=lambda one: None),
                tenant_id="t",
                platform=AdsPlatform.GOOGLE_ADS,
                account_id="a",
                access_token="token",
                scope="scope",
                connector_name="GoogleAdsConnector",
            )
        )


def test_token_get_supports_mapping_scalar_fallbacks_and_errors():
    with pytest.raises(AdsConnectorError, match="not configured"):
        run(
            shared.tokens_get_access_token_compat(
                tokens=None,
                tenant_id="t",
                platform=AdsPlatform.GOOGLE_ADS,
                account_id="a",
            )
        )

    class CanonicalStore:
        async def get(self, *, tenant_id, platform, account_id):
            return {"access_token": " canonical-token "}

    assert run(
        shared.tokens_get_access_token_compat(
            tokens=CanonicalStore(),
            tenant_id="t",
            platform=AdsPlatform.GOOGLE_ADS,
            account_id="a",
        )
    ) == "canonical-token"

    class LegacyStore:
        def get_access_token(self, tenant_id, platform, account_id):
            return {"token": "legacy-token"}

    assert run(
        shared.tokens_get_access_token_compat(
            tokens=LegacyStore(),
            tenant_id="t",
            platform=AdsPlatform.GOOGLE_ADS,
            account_id="a",
        )
    ) == "legacy-token"

    class FallthroughStore:
        def get_access_token(self, **payload):
            return " "

        def load(self, **payload):
            return "loaded-token"

    assert run(
        shared.tokens_get_access_token_compat(
            tokens=FallthroughStore(),
            tenant_id="t",
            platform=AdsPlatform.GOOGLE_ADS,
            account_id="a",
        )
    ) == "loaded-token"

    class BrokenStore:
        def get(self, **payload):
            raise TypeError("read transaction failed")

    with pytest.raises(TypeError, match="read transaction failed"):
        run(
            shared.tokens_get_access_token_compat(
                tokens=BrokenStore(),
                tenant_id="t",
                platform=AdsPlatform.GOOGLE_ADS,
                account_id="a",
            )
        )

    with pytest.raises(AdsConnectorError, match="no access_token"):
        run(
            shared.tokens_get_access_token_compat(
                tokens=SimpleNamespace(get=lambda **payload: None),
                tenant_id="t",
                platform=AdsPlatform.GOOGLE_ADS,
                account_id="a",
            )
        )


def test_http_compat_supports_sync_async_and_fail_closed_payloads():
    class SyncHttp:
        def post(self, url, *, headers, data):
            return {"method": "POST", "url": url, "data": data}

        def get(self, url, *, headers, params):
            return {"method": "GET", "url": url, "params": params}

    client = SyncHttp()
    assert run(
        shared.http_post_compat(
            client,
            platform=AdsPlatform.GOOGLE_ADS,
            url="https://post",
            headers={"x": "1"},
            data={"a": 1},
        )
    )["method"] == "POST"
    assert run(
        shared.http_get_compat(
            client,
            platform=AdsPlatform.GOOGLE_ADS,
            url="https://get",
            headers={"x": "1"},
            params={"a": 1},
        )
    )["method"] == "GET"

    request_calls = []

    class RequestHttp:
        async def request(self, method, url, **kwargs):
            request_calls.append((method, url, kwargs))
            return {"ok": True}

    request_client = RequestHttp()
    assert run(
        shared.http_post_compat(
            request_client,
            platform=AdsPlatform.META,
            url="p",
            headers={},
        )
    ) == {"ok": True}
    assert run(
        shared.http_get_compat(
            request_client,
            platform=AdsPlatform.META,
            url="g",
            headers={},
        )
    ) == {"ok": True}
    assert [call[0] for call in request_calls] == ["POST", "GET"]
    assert all(call[2]["platform"] == "meta" for call in request_calls)

    with pytest.raises(AdsConnectorError, match=r"post\(\) or request"):
        run(
            shared.http_post_compat(
                object(),
                platform=AdsPlatform.META,
                url="p",
                headers={},
            )
        )
    with pytest.raises(AdsConnectorError, match=r"get\(\) or request"):
        run(
            shared.http_get_compat(
                object(),
                platform=AdsPlatform.META,
                url="g",
                headers={},
            )
        )
    with pytest.raises(AdsConnectorError, match="mapping payload"):
        run(
            shared.http_get_compat(
                SimpleNamespace(get=lambda *args, **kwargs: ["not", "mapping"]),
                platform=AdsPlatform.META,
                url="g",
                headers={},
            )
        )


def test_url_secret_rows_and_summary_helpers():
    vault = SimpleNamespace(get_secret=lambda key: " vault-value ")
    assert shared.resolve_url_with_default(
        cfg_value=" config ",
        vault=vault,
        vault_key="k",
        default="default",
    ) == "config"
    assert shared.resolve_url_with_default(
        cfg_value=" ",
        vault=vault,
        vault_key="k",
        default="default",
    ) == "vault-value"
    assert shared.resolve_url_with_default(
        cfg_value=None,
        vault=None,
        vault_key="k",
        default="default",
    ) == "default"

    assert shared.resolve_url_required(
        cfg_value=" config ",
        vault=None,
        vault_key="k",
        error_message="missing",
    ) == "config"
    assert shared.resolve_url_required(
        cfg_value=None,
        vault=vault,
        vault_key="k",
        error_message="missing",
    ) == "vault-value"
    with pytest.raises(AdsConnectorError, match="missing"):
        shared.resolve_url_required(
            cfg_value=None,
            vault=None,
            vault_key="k",
            error_message="missing",
        )

    assert shared.resolve_secret_required(
        cfg_value=" secret ",
        vault=None,
        vault_key="k",
        error_message="missing secret",
    ) == "secret"
    assert shared.resolve_secret_required(
        cfg_value=None,
        vault=vault,
        vault_key="k",
        error_message="missing secret",
    ) == "vault-value"
    with pytest.raises(AdsConnectorError, match="missing secret"):
        shared.resolve_secret_required(
            cfg_value=None,
            vault=None,
            vault_key="k",
            error_message="missing secret",
        )

    assert shared.normalize_rows({"rows": {"id": 1}}, key="rows") == [{"id": 1}]
    assert shared.normalize_rows([{"id": 1}, "skip", {"id": 2}], key="rows") == [
        {"id": 1},
        {"id": 2},
    ]
    assert shared.normalize_rows("invalid", key="rows") == []
    assert shared.normalize_rows({"rows": 7}, key="rows") == []
    assert shared.normalize_rows(({"id": 3} for _ in range(1)), key="rows") == [
        {"id": 3}
    ]

    assert shared.summarize_rows(
        [
            {"spend": "2.5", "impressions": "100", "clicks": "10", "conversions": 2},
            {"spend": 1.5, "impressions": 100, "clicks": 10, "conversions": 1},
        ]
    ) == (4.0, 200, 0.1, 3)
    assert shared.summarize_rows(
        [{"spend": 0, "impressions": 0, "clicks": 25, "conversions": 0}]
    ) == (0.0, 0, 0.0, 0)


def test_opaque_signature_compatibility_fallbacks_and_errors():
    original_signature = shared.inspect.signature

    def unavailable(_method):
        raise ValueError("opaque callable")

    shared.inspect.signature = unavailable
    try:
        def positional(value, /):
            return value

        candidates = [((), {"value": "kw"}), (("positional",), {})]
        assert shared._call_sync_compat(positional, candidates) == "positional"
        assert run(shared._call_async_compat(positional, candidates)) == "positional"

        with pytest.raises(shared._NoCompatibleCall):
            shared._call_sync_compat(positional, [((), {"wrong": "x"})])
        with pytest.raises(shared._NoCompatibleCall):
            run(shared._call_async_compat(positional, [((), {"wrong": "x"})]))

        def internal_type_error(*args, **kwargs):
            raise TypeError("opaque backend failure")

        with pytest.raises(TypeError, match="opaque backend failure"):
            shared._call_sync_compat(internal_type_error, [((), {})])
        with pytest.raises(TypeError, match="opaque backend failure"):
            run(shared._call_async_compat(internal_type_error, [((), {})]))
    finally:
        shared.inspect.signature = original_signature


def test_token_get_skips_incompatible_methods():
    class IncompatibleStore:
        def get_access_token(self, one, two, three, four):
            return "unreachable"

    with pytest.raises(AdsConnectorError, match="no access_token"):
        run(
            shared.tokens_get_access_token_compat(
                tokens=IncompatibleStore(),
                tenant_id="t",
                platform=AdsPlatform.GOOGLE_ADS,
                account_id="a",
            )
        )

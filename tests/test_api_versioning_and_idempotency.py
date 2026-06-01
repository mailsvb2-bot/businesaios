from core.api.idempotency import IdempotencyKey, IdempotentEndpoint, MemoryIdempotencyStore
from core.api.versioning import DEFAULT_API_VERSION, ApiVersion
from core.tenancy.scope import TenantId


def test_api_version_parse_defaults():
    assert ApiVersion.parse(None, default=DEFAULT_API_VERSION) == DEFAULT_API_VERSION
    assert ApiVersion.parse("", default=DEFAULT_API_VERSION) == DEFAULT_API_VERSION
    assert ApiVersion.parse("v2.3", default=DEFAULT_API_VERSION) == ApiVersion(2, 3)
    assert ApiVersion.parse("2", default=DEFAULT_API_VERSION) == ApiVersion(2, 0)
    assert ApiVersion.parse("garbage", default=DEFAULT_API_VERSION) == DEFAULT_API_VERSION


def test_idempotent_endpoint_replay():
    store = MemoryIdempotencyStore()
    ep = IdempotentEndpoint(store, ttl_ms=60_000)
    key = IdempotencyKey(tenant_id=TenantId("t1"), key="k1")

    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        return {"ok": True, "value": 42}

    out1 = ep.call(key=key, fn=fn)
    out2 = ep.call(key=key, fn=fn)

    assert out1["value"] == 42
    assert out2["ok"] is True
    assert out2.get("idempotent_replay") is True
    assert calls["n"] == 1

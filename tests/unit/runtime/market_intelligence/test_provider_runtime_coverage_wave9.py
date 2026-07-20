from __future__ import annotations

import base64
from types import SimpleNamespace

import pytest

from runtime._internal.market_intelligence.http_transport import HttpTransportError
from runtime._internal.market_intelligence.provider_contracts import (
    ProviderAuthContract,
    ProviderAuthKind,
    ProviderCapabilityManifest,
    ProviderContractRegistry,
    ProviderErrorCode,
    ProviderRequestContract,
    ProviderSchemaContract,
)
from runtime._internal.market_intelligence.provider_runtime import (
    ProviderRuntimeError,
    ProviderRuntimeFactory,
    SecretReader,
    _bounded_positive_float,
    _bounded_positive_int,
    _is_missing_required,
    _normalize_tags,
    _text,
)


class Secrets:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def read(self, ref):
        return self.values.get(ref)


def contract(*, method="GET", required_query=(), required_body=(), allowed_query=("query",), allowed_body=()):
    return ProviderRequestContract(
        provider="provider-a",
        source_family="search_intelligence",
        operation="search",
        method=method,
        base_url="https://api.example/",
        path="/search",
        allowed_query_keys=allowed_query,
        required_query_keys=required_query,
        allowed_body_keys=allowed_body,
        required_body_keys=required_body,
        stable_version_header_name="X-Version",
        stable_version_header_value="v1",
    )


def schema(required=("query",)):
    return ProviderSchemaContract(
        provider="provider-a",
        source_family="search_intelligence",
        operation="search",
        input_required_fields=required,
        output_required_fields=("external_id", "title"),
    )


def factory(*, auth=None, request=None, schema_contract=None, secrets=None):
    registry = ProviderContractRegistry()
    registry.register_alias("alias-a", "provider-a")
    registry.register_manifest(
        ProviderCapabilityManifest(
            provider="provider-a",
            source_family="search_intelligence",
            supported_operations=("search",),
            version="v9",
        )
    )
    registry.register_request_contract(request or contract(required_query=("query",)))
    registry.register_schema_contract(schema_contract or schema())
    registry.register_auth_contract(auth or ProviderAuthContract(provider="provider-a"))
    out = object.__new__(ProviderRuntimeFactory)
    out.registry = registry
    out.secrets = secrets or Secrets()
    return out


def test_helpers_and_secret_reader(monkeypatch):
    assert _text(None, default="x") == "x"
    assert _is_missing_required(None)
    assert _is_missing_required("  ")
    assert not _is_missing_required([])
    assert _bounded_positive_int("bad", default=20, upper=100) == 20
    assert _bounded_positive_int(500, default=20, upper=100) == 100
    assert _bounded_positive_float("bad", default=20, upper=120) == 20
    assert _bounded_positive_float(0, default=20, upper=120) == 20
    assert _bounded_positive_float(999, default=20, upper=120) == 120
    monkeypatch.setenv("TOKEN_ENV", " secret ")
    reader = SecretReader()
    assert reader.read(None) is None
    assert reader.read("TOKEN_ENV") == "secret"
    assert reader.read("MISSING") is None


def test_build_plan_alias_bounds_and_unhashable_values():
    f = factory(
        request=contract(
            method="POST",
            required_query=("query",),
            required_body=("filters",),
            allowed_query=("query", "filters"),
            allowed_body=("filters",),
        ),
        schema_contract=schema(("query", "filters")),
    )
    plan = f.build_plan(
        provider="alias-a",
        operation="search",
        payload={
            "query": ["one", "two"],
            "filters": {"region": "eu"},
            "timeout_seconds": "bad",
            "max_pages": 1000,
        },
    )
    assert plan.provider == "provider-a"
    assert plan.request.url == "https://api.example/search"
    assert plan.request.params["query"] == ["one", "two"]
    assert plan.request.body == {"filters": {"region": "eu"}}
    assert plan.request.timeout_seconds == 20.0
    assert plan.max_pages == 100
    assert plan.manifest["version"] == "v9"


@pytest.mark.parametrize("value", [None, "", "   "])
def test_required_fields_fail_closed(value):
    f = factory()
    with pytest.raises(ProviderRuntimeError, match="missing required input"):
        f.build_plan(provider="provider-a", operation="search", payload={"query": value})


def test_query_body_and_auth_contracts():
    req = contract(required_query=("query",))
    f = factory(
        auth=ProviderAuthContract(
            provider="provider-a",
            auth_kind=ProviderAuthKind.API_KEY_QUERY,
            secret_ref_primary="API_KEY",
            query_param_name="key",
        ),
        secrets=Secrets({"API_KEY": "q-secret"}),
    )
    assert f._build_query_params(payload={"query": "x"}, request_contract=req, auth=f.registry.auth_contract("provider-a")) == {
        "query": "x",
        "key": "q-secret",
    }
    f.secrets = Secrets()
    with pytest.raises(ProviderRuntimeError, match="missing provider query"):
        f._build_query_params(payload={"query": "x"}, request_contract=req, auth=f.registry.auth_contract("provider-a"))

    get_req = contract(method="GET")
    assert f._build_body(payload={}, request_contract=get_req) is None
    post_req = contract(method="POST", allowed_body=("payload",), required_body=("payload",))
    assert f._build_body(payload={"payload": [1, 2]}, request_contract=post_req) == {"payload": [1, 2]}
    with pytest.raises(ProviderRuntimeError, match="missing required body"):
        f._build_body(payload={"payload": "  "}, request_contract=post_req)


@pytest.mark.parametrize(
    ("auth", "values", "expected"),
    [
        (ProviderAuthContract(provider="p"), {}, {"X-Version": "v1"}),
        (
            ProviderAuthContract(provider="p", auth_kind=ProviderAuthKind.API_KEY_HEADER, secret_ref_primary="K", header_name="X-Key", header_value_template="Key {secret}"),
            {"K": "s"},
            {"X-Version": "v1", "X-Key": "Key s"},
        ),
        (
            ProviderAuthContract(provider="p", auth_kind=ProviderAuthKind.BEARER_TOKEN, secret_ref_primary="K"),
            {"K": "s"},
            {"X-Version": "v1", "Authorization": "Bearer s"},
        ),
        (
            ProviderAuthContract(provider="p", auth_kind=ProviderAuthKind.BASIC, basic_username_ref="U", basic_password_ref="P"),
            {"U": "user", "P": "pass"},
            {"X-Version": "v1", "Authorization": "Basic " + base64.b64encode(b"user:pass").decode("ascii")},
        ),
    ],
)
def test_header_auth_variants(auth, values, expected):
    f = factory(secrets=Secrets(values))
    assert f._build_headers(auth=auth, request_contract=contract()) == expected


@pytest.mark.parametrize(
    "auth",
    [
        ProviderAuthContract(provider="p", auth_kind=ProviderAuthKind.API_KEY_HEADER, secret_ref_primary="K"),
        ProviderAuthContract(provider="p", auth_kind=ProviderAuthKind.BEARER_TOKEN, secret_ref_primary="K"),
        ProviderAuthContract(provider="p", auth_kind=ProviderAuthKind.BASIC, basic_username_ref="U", basic_password_ref="P"),
    ],
)
def test_header_auth_missing_secrets(auth):
    with pytest.raises(ProviderRuntimeError, match="missing provider"):
        factory()._build_headers(auth=auth, request_contract=contract())


def test_normalize_records_and_tag_contracts():
    f = factory()
    records = f.normalize_records(
        provider="provider-a",
        operation="search",
        source_family="search_intelligence",
        records=[
            {"id": "1", "name": "One", "description": "Body", "tags": " Alpha ", "created_at": "t1", "type": "x"},
            {"uuid": "2", "headline": "Two", "text": "Text", "tags": ["B", "a", "B"], "landing_url": "u", "status": "ok"},
            {"slug": "3", "copy": "Copy", "tags": None},
        ],
    )
    assert records[0]["tags"] == ("alpha",)
    assert records[1]["tags"] == ("a", "b")
    assert records[2]["tags"] == ()
    assert records[0]["evidence"]["provider_version"] == "v9"
    with pytest.raises(ProviderRuntimeError, match="stable identity"):
        f.normalize_records(provider="provider-a", operation="search", source_family="x", records=[{}])
    with pytest.raises(ProviderRuntimeError, match="tags must"):
        f.normalize_records(provider="provider-a", operation="search", source_family="x", records=[{"id": "1", "tags": {"bad": True}}])


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (401, ProviderErrorCode.AUTH_INVALID.value),
        (403, ProviderErrorCode.FORBIDDEN.value),
        (404, ProviderErrorCode.NOT_FOUND.value),
        (429, ProviderErrorCode.RATE_LIMITED.value),
        (500, ProviderErrorCode.TEMPORARY_UNAVAILABLE.value),
        (400, ProviderErrorCode.TRANSPORT_ERROR.value),
    ],
)
def test_transport_error_mapping(status, code):
    mapped = factory().map_transport_error(provider="p", exc=HttpTransportError("x", "boom", status_code=status, payload={"a": 1}))
    assert mapped.code == code and mapped.details == {"a": 1}
    generic = factory().map_transport_error(provider="p", exc=ValueError("bad"))
    assert generic.code == ProviderErrorCode.TRANSPORT_ERROR.value


def test_supports_bootstrap_and_catalog_helpers(monkeypatch):
    f = factory()
    assert f.supports_provider("provider-a")
    assert not f.supports_provider("missing")
    assert f._allowed_query_keys("landing_intelligence", "scan")[0] == "subject_url"
    assert f._allowed_query_keys("app_store", "scan") == f._allowed_query_keys("other", "scan")
    assert f._required_query_keys("competitor_analytics", "scan") == ("subject_url",)
    assert f._required_query_keys("other", "scan") == ("query",)
    assert f._required_input_fields("other", "scan") == ("query",)

    entry = SimpleNamespace(
        provider="custom",
        source_family="landing_intelligence",
        env_base_url_key="CUSTOM_BASE",
        default_base_url="https://default",
        stable_version_header_name="X-V",
        stable_version_header_value="1",
    )
    monkeypatch.setenv("CUSTOM_BASE", "https://override")
    built = f._build_request_contract(entry=entry, operation="scan")
    assert built.base_url == "https://override" and built.required_query_keys == ("subject_url",)
    schema_built = f._build_schema_contract(entry=entry, operation="scan")
    assert schema_built.input_required_fields == ("subject_url",)

    bootstrapped = ProviderRuntimeFactory()
    assert bootstrapped.registry.snapshot()["providers"]


def test_remaining_header_query_and_body_branches():
    f = factory()
    req_without_version = ProviderRequestContract(
        provider="provider-a",
        source_family="search_intelligence",
        operation="search",
        method="POST",
        base_url="https://api.example",
        path="/search",
        allowed_query_keys=("optional",),
        required_query_keys=("required",),
        allowed_body_keys=("optional",),
    )
    unknown_auth = SimpleNamespace(auth_kind="future", provider="provider-a")
    assert f._build_headers(auth=unknown_auth, request_contract=req_without_version) == {}
    with pytest.raises(ProviderRuntimeError, match="missing required query"):
        f._build_query_params(
            payload={"optional": None, "required": " "},
            request_contract=req_without_version,
            auth=ProviderAuthContract(provider="provider-a"),
        )
    assert f._build_body(payload={"optional": None}, request_contract=req_without_version) == {}
    with pytest.raises(ProviderRuntimeError, match="tags must"):
        _normalize_tags(bytearray(), provider="p", operation="o")

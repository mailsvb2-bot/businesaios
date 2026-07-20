from __future__ import annotations

from collections.abc import Mapping

import pytest

from execution.market_intelligence_connector_resolver import MarketIntelligenceConnectorResolver
from interfaces.common.auth_session import AuthSession
from interfaces.market_intelligence.base import (
    MarketIntelConnectorBase,
    ProviderClientProtocol,
    _bounded_limit,
    _normalize_tags,
    _safe_dict,
    _safe_list,
    _safe_text,
)


class Provider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def execute_market_intelligence(self, **kwargs):
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


class RateLimit:
    def __init__(self, allowed=True):
        self.allowed = allowed
        self.keys = []

    def allow(self, key):
        self.keys.append(key)
        return self.allowed


def connector(provider=None, **changes):
    values = {
        "connector_name": "amazon_market_intelligence",
        "connector_id": "market_intelligence.amazon",
        "provider_key": "amazon",
        "source_family": "marketplace",
        "provider_client": provider if provider is not None else Provider([{"records": []}]),
    }
    values.update(changes)
    return MarketIntelConnectorBase(**values)


def valid_payload(**changes):
    payload = {
        "tenant_id": "tenant-a",
        "query": "shoes",
        "limit": 10,
        "metadata": {"origin": "test"},
    }
    payload.update(changes)
    return payload


def valid_result(**changes):
    payload = {
        "connector_id": "market_intelligence.amazon",
        "provider": "amazon",
        "source_family": "marketplace",
        "operation": "sync_catalog",
        "target": {
            "tenant_id": "tenant-a",
            "query": "shoes",
            "subject_url": None,
        },
        "records": [{"external_id": "r-1"}],
    }
    payload.update(changes)
    return payload


def test_protocol_and_safe_helpers():
    assert ProviderClientProtocol.execute_market_intelligence(
        object(),
        provider="p",
        source_family="marketplace",
        operation="sync_catalog",
        payload={},
        dry_run=False,
    ) is None
    assert _safe_dict({"a": 1}) == {"a": 1}
    assert _safe_dict(None) == {}
    assert _safe_list([{"a": 1}, 2]) == [{"a": 1}]
    assert _safe_list(({"b": 2}, 3)) == [{"b": 2}]
    assert _safe_list("bad") == []
    assert _safe_text(" x ") == "x"
    assert _safe_text(" ") is None

    assert _bounded_limit(None) == 25
    assert _bounded_limit("250") == 250
    assert _bounded_limit(-5) == 1
    assert _bounded_limit(999) == 250
    with pytest.raises(ValueError, match="integer"):
        _bounded_limit(True)
    with pytest.raises(ValueError, match="integer"):
        _bounded_limit("bad")
    with pytest.raises(ValueError, match="integer"):
        _bounded_limit(1.5)

    defaults = ("marketplace", "amazon")
    assert _normalize_tags(None, defaults=defaults) == defaults
    assert _normalize_tags(" featured ", defaults=defaults) == ("featured",)
    assert _normalize_tags(" ", defaults=defaults) == defaults
    assert _normalize_tags(["a", " ", 2], defaults=defaults) == ("a", "2")
    assert _normalize_tags([], defaults=defaults) == defaults
    with pytest.raises(ValueError, match="tags"):
        _normalize_tags({"bad": True}, defaults=defaults)


def test_post_init_validates_identity_and_uses_factory(monkeypatch):
    fake = Provider([{"records": []}])
    monkeypatch.setattr("interfaces.market_intelligence.provider_factory.build_default_provider_client", lambda provider: fake)
    built = MarketIntelConnectorBase(
        connector_name=" ",
        connector_id=" id ",
        provider_key=" amazon ",
        source_family=" marketplace ",
        version=" ",
        provider_client=None,
    )
    assert built.provider_client is fake
    assert built.connector_name == "market_intelligence"
    assert built.connector_id == "id"
    assert built.provider_key == "amazon"
    assert built.version == "v1"
    assert built.session.configured is True

    configured = connector(session=AuthSession(account_id="kept", configured=True))
    assert configured.session.account_id == "kept"

    with pytest.raises(ValueError, match="connector_id"):
        connector(connector_id=" ")
    with pytest.raises(ValueError, match="provider_key"):
        connector(provider_key=" ")
    with pytest.raises(ValueError, match="source_family"):
        connector(source_family="future")


def test_dry_run_enforces_canonical_connector_contract(monkeypatch):
    shell = connector()
    shell.rate_limit_guard = RateLimit()
    result = shell.execute(" sync_catalog ", valid_payload(), idempotency_key="idem", dry_run=True)
    assert result.ok is True
    assert result.code == "dry_run"
    assert result.payload["dry_run"] is True
    assert result.payload["target"]["tenant_id"] == "tenant-a"
    assert result.payload["records"][0]["external_id"] == "preview:amazon:sync_catalog"
    assert result.payload["idempotency_key"] == "idem"
    assert shell.rate_limit_guard.keys == ["amazon_market_intelligence:sync_catalog"]

    assert shell.execute(" ", {}, dry_run=True).code == "invalid_operation"
    assert shell.execute("sync_catalog", [], dry_run=True).code == "invalid_payload"  # type: ignore[arg-type]

    limited = connector()
    limited.rate_limit_guard = RateLimit(False)
    assert limited.execute("sync_catalog", {}, dry_run=True).code == "rate_limited"

    no_dry = connector(support_dry_run=False)
    assert no_dry.execute("sync_catalog", {}, dry_run=True).code == "dry_run_not_supported"

    no_idempotency = connector(support_idempotency=False)
    assert no_idempotency.execute("sync_catalog", {}, idempotency_key="x", dry_run=True).code == "idempotency_not_supported"

    assert shell.execute("future_operation", {}, dry_run=True).code == "unsupported_operation"
    assert shell.execute("sync_catalog", {"limit": "bad"}, dry_run=True).code == "invalid_payload"
    assert shell.execute("sync_catalog", {"metadata": []}, dry_run=True).code == "invalid_payload"

    shell.decide = lambda: None  # type: ignore[attr-defined]
    with pytest.raises(RuntimeError, match="decide"):
        shell.execute("sync_catalog", {}, dry_run=True)


def test_capabilities_maturity_and_health(monkeypatch):
    real = connector()
    assert real.connector_maturity().value == "real"
    capabilities = real.connector_capabilities()
    assert capabilities.read is True and capabilities.write is False
    assert capabilities.metadata["operation_names"][0] == "sync_catalog"
    assert real.health().reason == "provider_configured"

    monkeypatch.setattr("interfaces.market_intelligence.provider_factory.build_default_provider_client", lambda provider: None)
    shell = MarketIntelConnectorBase(
        connector_id="shell",
        provider_key="amazon",
        source_family="marketplace",
        provider_client=None,
    )
    assert shell.connector_maturity().value == "capability_shell"
    assert shell.health().healthy is True
    assert shell.health().reason == "dry_run_only"
    shell.support_dry_run = False
    assert shell.health().healthy is False
    assert shell.health().reason == "not_configured"


def test_execute_configured_provider_fail_closed_paths(monkeypatch):
    unsupported = connector()
    assert unsupported._execute_configured("bad", {}).code == "unsupported_operation"
    assert unsupported._execute_configured("sync_catalog", {"limit": "bad"}).code == "invalid_payload"

    monkeypatch.setattr("interfaces.market_intelligence.provider_factory.build_default_provider_client", lambda provider: None)
    missing = MarketIntelConnectorBase(
        connector_id="missing",
        provider_key="amazon",
        source_family="marketplace",
        provider_client=None,
        session=AuthSession(account_id="manual", configured=True),
    )
    assert missing._execute_configured("sync_catalog", {}).code == "not_configured"

    assert connector(Provider([TimeoutError()])).execute("sync_catalog", {}).code == "temporary_unavailable"
    assert connector(Provider([RuntimeError()])).execute("sync_catalog", {}).code == "provider_error"
    assert connector(Provider([["not", "mapping"]])).execute("sync_catalog", {}).code == "provider_contract_error"
    assert connector(Provider([{"ok": False, "code": "rejected", "message": "no"}])).execute("sync_catalog", {}).code == "rejected"
    assert connector(Provider([{"executed": False}])).execute("sync_catalog", {}).code == "provider_error"
    assert connector(Provider([{"status": "failed"}])).execute("sync_catalog", {}).code == "provider_error"
    assert connector(Provider([{"records": "bad"}])).execute("sync_catalog", {}).code == "provider_contract_error"
    assert connector(Provider([{"records": [1]}])).execute("sync_catalog", {}).code == "provider_contract_error"
    assert connector(Provider([{"records": [{"id": "1", "tags": {"bad": True}}]}])).execute("sync_catalog", {}).code == "provider_contract_error"


def test_execute_success_and_empty_provider_envelopes():
    provider = Provider(
        [
            {
                "records": [
                    {
                        "id": "1",
                        "headline": "Headline",
                        "description": "Body",
                        "landing_url": "https://example.test",
                        "price": "12.5",
                        "rating": "4.5",
                        "currency": " EUR ",
                        "evidence": {"source": "provider"},
                        "metadata": {"rank": 1},
                        "tags": "featured",
                    },
                    {"title": "Fallback id", "tags": []},
                ],
                "cursor": " next ",
                "status": "ok",
                "metadata": {"request_id": "p-1"},
            },
            {"records": []},
        ]
    )
    live = connector(provider)
    first = live.execute("sync_catalog", valid_payload())
    assert first.ok is True
    assert first.payload["records"][0]["external_id"] == "1"
    assert first.payload["records"][0]["tags"] == ["featured"]
    assert first.payload["records"][1]["external_id"] == "amazon:1"
    assert first.payload["cursor"] == "next"
    assert first.payload["summary"]["records_count"] == 2
    assert provider.calls[0]["dry_run"] is False

    second = live.execute("sync_catalog", {"subject_url": "https://subject.test"})
    assert second.payload["records"][0]["external_id"] == "empty:amazon:sync_catalog"
    assert second.payload["records"][0]["tags"] == ["amazon", "empty", "marketplace"]


def test_verification_rejects_incomplete_or_conflicting_evidence():
    live = connector()
    assert live.verify("sync_catalog", {}, {}).code == "verification_missing_fields"
    assert live.verify("sync_catalog", {}, valid_result(connector_id="other")).code == "verification_connector_mismatch"
    assert live.verify("sync_catalog", {}, valid_result(provider="other")).code == "verification_provider_mismatch"
    assert live.verify("sync_catalog", {}, valid_result(source_family="ads_library")).code == "verification_family_mismatch"
    assert live.verify("sync_catalog", {}, valid_result(operation="fetch_listing")).code == "verification_operation_mismatch"
    assert live.verify("sync_catalog", {}, valid_result(records="bad")).code == "verification_records_invalid"
    assert live.verify("sync_catalog", {}, valid_result(records=[1])).code == "verification_records_invalid"
    assert live.verify("sync_catalog", {}, valid_result(records=[{"external_id": "ok"}, {}])).code == "verification_record_identity_missing"
    assert live.verify("sync_catalog", {"query": "shoes"}, valid_result(target=None)).code == "verification_target_missing"
    assert live.verify("sync_catalog", {"query": "boots"}, valid_result()).code == "verification_query_mismatch"
    assert live.verify(
        "sync_catalog",
        {"subject_url": "https://requested.test"},
        valid_result(target={"tenant_id": "tenant-a", "subject_url": "https://other.test"}),
    ).code == "verification_subject_mismatch"
    assert live.verify(
        "sync_catalog",
        {"tenant_id": "tenant-b"},
        valid_result(),
    ).code == "verification_tenant_mismatch"

    verified = live.verify("sync_catalog", valid_payload(), valid_result())
    assert verified.ok is True
    assert verified.code == "verified"
    assert verified.payload["records_count"] == 1


def test_target_and_envelope_helpers():
    live = connector()
    target = live._build_target(
        {
            "tenant": "tenant-b",
            "url": "https://example.test",
            "handle": "acct",
            "region": " eu ",
            "locale": " en ",
            "limit": 500,
        }
    )
    assert target.tenant_id == "tenant-b"
    assert target.subject_url == "https://example.test"
    assert target.account_ref == "acct"
    assert target.limit == 250

    preview = live._build_dry_run_envelope(operation="sync_catalog", target=target, payload={1: "x"})
    assert preview.metadata == {"mode": "dry_run"}
    assert preview.records[0].metadata["requested_payload_keys"] == ["1"]

    result = live._to_result(ok=True, code="ok", message="done", envelope=preview, dry_run=False)
    assert result.payload["capability_family"] == "market_intelligence"
    assert live._operation_names()[-1] == "fetch_images"


def test_connector_resolver_known_and_unknown_provider():
    marker = object()
    resolver = MarketIntelligenceConnectorResolver(factories={"known": lambda: marker})
    assert resolver.build(" known ") is marker
    with pytest.raises(KeyError, match="unknown market_intelligence provider"):
        resolver.build(" missing ")
    assert isinstance(MarketIntelligenceConnectorResolver().factories, Mapping)

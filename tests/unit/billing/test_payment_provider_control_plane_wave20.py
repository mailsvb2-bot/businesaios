from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta, tzinfo
from threading import Thread
from types import SimpleNamespace

import pytest

from billing.payment_provider_capability import PaymentProviderCapabilities
from billing.payment_provider_health_registry import (
    PaymentProviderHealthRegistry,
    ProviderHealthStatus,
)
from billing.payment_provider_registry import (
    PaymentProviderRegistration,
    PaymentProviderRegistry,
)
from billing.payment_provider_router import PaymentProviderRouter, PaymentProviderSelection

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _Provider:
    def __init__(self, name: str) -> None:
        self.name = name

    def provider_name(self) -> str:
        return self.name

    def ensure_customer(self, **kwargs):
        raise NotImplementedError

    def collect(self, attempt):
        raise NotImplementedError

    def refund(self, **kwargs):
        raise NotImplementedError


class _NoOffset(tzinfo):
    def utcoffset(self, dt):
        return None

    def dst(self, dt):
        return None


def _registration(
    name: str = "Alpha",
    *,
    priority: int = 10,
    currencies: tuple[str, ...] = ("usd", "EUR"),
    tenants: tuple[str, ...] = ("tenant-a",),
    operations: tuple[str, ...] = ("collect", "refund"),
    strict: bool = False,
    metadata=None,
) -> PaymentProviderRegistration:
    return PaymentProviderRegistration(
        provider_name=name,
        provider=_Provider(name.lower()),
        currencies=currencies,
        priority=priority,
        tenant_allowlist=tenants,
        metadata={"nested": {"value": 1}} if metadata is None else metadata,
        capabilities=PaymentProviderCapabilities(
            operations=operations,
            strict_affinity_for_refund=strict,
            metadata={"nested": {"flag": True}},
        ),
        backend_key=f" {name}_backend ",
    )


def test_capability_normalization_and_fail_closed_validation() -> None:
    source = PaymentProviderCapabilities(
        operations=(" REFUND ", "collect"),
        strict_affinity_for_refund=True,
        metadata={"nested": {"value": 1}},
    )
    normalized = source.normalized_copy()
    assert normalized.operations == ("collect", "refund")
    assert normalized.supports(" REFUND ") is True
    assert normalized.supports("ensure_customer") is False
    normalized.metadata["nested"]["value"] = 9
    assert source.metadata["nested"]["value"] == 1

    invalid = [
        replace(source, operations=["collect"]),
        replace(source, operations=(1,)),
        replace(source, operations=(" ",)),
        replace(source, operations=("collect", "COLLECT")),
        replace(source, operations=("capture",)),
        replace(source, strict_affinity_for_refund=1),
        replace(source, metadata=[]),
    ]
    for value in invalid:
        with pytest.raises(ValueError):
            value.validate()
    with pytest.raises(ValueError, match="operation must be a string"):
        normalized.supports(1)
    with pytest.raises(ValueError, match="operation is required"):
        normalized.supports(" ")


def test_registration_normalization_support_and_affinity() -> None:
    source = _registration()
    normalized = source.normalized_copy()
    assert normalized.provider_name == "Alpha"
    assert normalized.currencies == ("EUR", "USD")
    assert normalized.tenant_allowlist == ("tenant-a",)
    assert normalized.backend_key == "alpha_backend"
    assert normalized.supports(tenant_id="tenant-a", currency="usd") is True
    assert normalized.supports(tenant_id="tenant-b", currency="USD") is False
    assert normalized.supports(tenant_id="tenant-a", currency="GBP") is False
    assert normalized.supports_operation(operation="collect") is True
    assert normalized.supports_operation(operation="ensure_customer") is False
    assert normalized.supports_operation(operation="refund") is True
    normalized.metadata["nested"]["value"] = 7
    normalized.capabilities.metadata["nested"]["flag"] = False
    assert source.metadata["nested"]["value"] == 1
    assert source.capabilities.metadata["nested"]["flag"] is True

    strict = _registration(strict=True).normalized_copy()
    assert strict.supports_operation(operation="refund") is False
    assert strict.supports_operation(
        operation="refund", metadata={"preferred_provider": "alpha"}
    ) is True
    assert strict.supports_operation(
        operation="refund", metadata={"provider_customer_id": "alpha:cust"}
    ) is True
    assert strict.supports_operation(
        operation="refund", metadata={"provider_name_hint": "beta"}
    ) is False
    non_strict = _registration(strict=False).normalized_copy()
    assert non_strict.supports_operation(
        operation="refund",
        metadata={"strict_provider_affinity": True, "preferred_provider": "Alpha"},
    ) is True
    assert non_strict.supports_operation(
        operation="refund", metadata={"strict_provider_affinity": True}
    ) is False


@pytest.mark.parametrize(
    "registration",
    [
        replace(_registration(), provider_name=" "),
        replace(_registration(), provider=object()),
        replace(_registration(), provider=SimpleNamespace(provider_name=lambda: "")),
        replace(_registration(), provider=SimpleNamespace(provider_name=lambda: 1)),
        replace(_registration(), provider=SimpleNamespace(provider_name=lambda: "other")),
        replace(_registration(), priority=True),
        replace(_registration(), priority=-1),
        replace(_registration(), currencies="USD"),
        replace(_registration(), currencies={"USD": True}),
        replace(_registration(), currencies=(1,)),
        replace(_registration(), currencies=(" ",)),
        replace(_registration(), currencies=("usd", "USD")),
        replace(_registration(), tenant_allowlist="tenant-a"),
        replace(_registration(), tenant_allowlist={"tenant-a": True}),
        replace(_registration(), tenant_allowlist=(1,)),
        replace(_registration(), tenant_allowlist=(" ",)),
        replace(_registration(), tenant_allowlist=("tenant-a", "tenant-a")),
        replace(_registration(), metadata=[]),
        replace(_registration(), capabilities=object()),
        replace(_registration(), backend_key=" "),
    ],
)
def test_registration_rejects_malformed_configuration(registration) -> None:
    with pytest.raises(ValueError):
        registration.validate()


def test_registration_rejects_malformed_runtime_queries() -> None:
    registration = _registration().normalized_copy()
    for tenant, currency in ((1, "USD"), (" ", "USD"), ("tenant-a", 1), ("tenant-a", " ")):
        with pytest.raises(ValueError):
            registration.supports(tenant_id=tenant, currency=currency)
    with pytest.raises(ValueError, match="operation must be a string"):
        registration.supports_operation(operation=1)
    with pytest.raises(ValueError, match="operation is required"):
        registration.supports_operation(operation=" ")
    with pytest.raises(ValueError, match="metadata must be a mapping"):
        registration.supports_operation(operation="refund", metadata=[])
    with pytest.raises(ValueError, match="strict_provider_affinity"):
        registration.supports_operation(
            operation="refund", metadata={"strict_provider_affinity": "yes"}
        )
    with pytest.raises(ValueError, match="preferred provider affinity"):
        registration.supports_operation(
            operation="refund",
            metadata={"strict_provider_affinity": True, "preferred_provider": 7},
        )
    with pytest.raises(ValueError, match="provider_customer_id"):
        registration.supports_operation(
            operation="refund",
            metadata={"strict_provider_affinity": True, "provider_customer_id": 7},
        )


def test_registry_is_thread_safe_idempotent_and_returns_snapshots() -> None:
    for invalid in ("alpha", 1, {"alpha": 1}):
        with pytest.raises(ValueError):
            PaymentProviderRegistry(invalid)
    registry = PaymentProviderRegistry()
    with pytest.raises(ValueError):
        registry.register(object())
    alpha_registration = _registration("Alpha", priority=20)
    alpha = registry.register(alpha_registration)
    assert registry.register(alpha_registration) == alpha
    with pytest.raises(ValueError, match="different configuration"):
        registry.register(_registration("Alpha", priority=21))
    with pytest.raises(ValueError, match="provider_name is required"):
        registry.get(" ")
    with pytest.raises(LookupError, match="unknown provider"):
        registry.get("missing")

    def add(name: str, priority: int) -> None:
        registry.register(_registration(name, priority=priority, tenants=()))

    threads = [Thread(target=add, args=(f"P{index}", index)) for index in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    listed = registry.list_registrations()
    assert [item.provider_name for item in listed[:5]] == ["P0", "P1", "P2", "P3", "P4"]
    fetched = registry.get("alpha")
    fetched.metadata["nested"]["value"] = 99
    assert registry.get("alpha").metadata["nested"]["value"] == 1


def test_health_status_and_registry_fail_closed() -> None:
    healthy = ProviderHealthStatus(provider_name=" Alpha ", metadata={"nested": {"v": 1}})
    copy = healthy.normalized_copy()
    assert copy.provider_name == "alpha"
    copy.metadata["nested"]["v"] = 2
    assert healthy.metadata["nested"]["v"] == 1

    invalid = [
        replace(healthy, provider_name=" "),
        replace(healthy, healthy=1),
        replace(healthy, cooldown_until=datetime(2026, 1, 1)),
        replace(healthy, cooldown_until=datetime(2026, 1, 1, tzinfo=_NoOffset())),
        replace(healthy, failure_count=True),
        replace(healthy, failure_count=-1),
        replace(healthy, last_failure_reason=" "),
        replace(healthy, metadata=[]),
        replace(healthy, failure_count=1),
        replace(healthy, cooldown_until=NOW),
        replace(healthy, last_failure_reason="boom"),
        ProviderHealthStatus(provider_name="a", healthy=False, failure_count=0),
        ProviderHealthStatus(provider_name="a", healthy=False, failure_count=1),
        ProviderHealthStatus(
            provider_name="a", healthy=False, failure_count=1, cooldown_until=NOW
        ),
    ]
    for status in invalid:
        with pytest.raises(ValueError):
            status.validate()

    registry = PaymentProviderHealthRegistry()
    assert registry.get("ALPHA").healthy is True
    with pytest.raises(ValueError):
        registry.get(1)
    with pytest.raises(ValueError):
        registry.mark_failure("alpha", reason=" ")
    with pytest.raises(ValueError):
        registry.mark_failure("alpha", reason="boom", cooldown_seconds=True)
    with pytest.raises(ValueError):
        registry.mark_failure("alpha", reason="boom", now=datetime(2026, 1, 1))
    failed = registry.mark_failure("alpha", reason=" boom ", cooldown_seconds=10, now=NOW)
    assert failed.failure_count == 1 and failed.last_failure_reason == "boom"
    assert registry.is_available("alpha", now=NOW + timedelta(seconds=9)) is False
    assert registry.is_available("alpha", now=NOW + timedelta(seconds=10)) is True
    failed_again = registry.mark_failure("alpha", reason="again", cooldown_seconds=0, now=NOW)
    assert failed_again.failure_count == 2
    assert registry.is_available("alpha", now=NOW) is True
    success = registry.mark_success("alpha")
    assert success.healthy is True and registry.is_available("alpha", now=NOW) is True


def test_router_filters_orders_resolves_and_tracks_health() -> None:
    alpha = _registration("Alpha", priority=20, tenants=(), strict=True)
    beta = _registration("Beta", priority=10, tenants=(), currencies=("USD",))
    tenant_only = _registration("TenantOnly", priority=0, tenants=("tenant-b",))
    registry = PaymentProviderRegistry((alpha, beta, tenant_only))
    health = PaymentProviderHealthRegistry()
    router = PaymentProviderRouter(registry=registry, health_registry=health)

    candidates = router.list_candidates(
        tenant_id="tenant-a", currency="usd", operation="collect", now=NOW
    )
    assert [item.provider_name for item in candidates] == ["Beta", "Alpha"]
    assert candidates[0].currency == "USD"
    assert router.route_payment_provider(
        tenant_id="tenant-a", currency="USD", operation="collect", now=NOW
    ).provider_name == "Beta"
    assert router.select(
        tenant_id="tenant-a", currency="USD", operation="collect", now=NOW
    ).provider_name == "Beta"
    assert router.resolve_provider(
        tenant_id="tenant-a", currency="USD", operation="collect", now=NOW
    ).provider_name() == "beta"
    assert [provider.provider_name() for provider in router.resolve_providers(
        tenant_id="tenant-a", currency="USD", operation="collect", now=NOW
    )] == ["beta", "alpha"]

    router.mark_provider_failure("Beta", reason="timeout", cooldown_seconds=10, now=NOW)
    assert router.route_payment_provider(
        tenant_id="tenant-a", currency="USD", operation="collect", now=NOW
    ).provider_name == "Alpha"
    after_cooldown = router.list_candidates(
        tenant_id="tenant-a", currency="USD", operation="collect", now=NOW + timedelta(seconds=10)
    )
    assert [item.provider_name for item in after_cooldown] == ["Beta", "Alpha"]
    assert after_cooldown[0].metadata["failure_count"] == 1
    router.mark_provider_success("Beta")

    strict = router.list_candidates(
        tenant_id="tenant-a",
        currency="USD",
        operation="refund",
        metadata={"preferred_provider": "Alpha", "strict_provider_affinity": True},
        now=NOW,
    )
    assert [item.provider_name for item in strict] == ["Alpha"]
    assert router.list_candidates(
        tenant_id="tenant-a", currency="EUR", operation="collect", now=NOW
    )[0].provider_name == "Alpha"
    with pytest.raises(LookupError, match="no payment provider"):
        router.route_payment_provider(
            tenant_id="tenant-a", currency="JPY", operation="collect", now=NOW
        )


def test_router_rejects_malformed_inputs_and_selection_state() -> None:
    registry = PaymentProviderRegistry((_registration(tenants=()),))
    with pytest.raises(ValueError):
        PaymentProviderRouter(registry=object())
    with pytest.raises(ValueError):
        PaymentProviderRouter(registry=registry, health_registry=object())
    router = PaymentProviderRouter(registry=registry)

    invalid_selections = [
        PaymentProviderSelection(1, "USD", "a"),
        PaymentProviderSelection("", "USD", "a"),
        PaymentProviderSelection("tenant-a", "", "a"),
        PaymentProviderSelection("tenant-a", "usd", "a"),
        PaymentProviderSelection("tenant-a", "USD", ""),
        PaymentProviderSelection("tenant-a", "USD", "a", metadata=[]),
    ]
    for selection in invalid_selections:
        with pytest.raises(ValueError):
            selection.validate()

    calls = [
        {"tenant_id": 1, "currency": "USD"},
        {"tenant_id": "", "currency": "USD"},
        {"tenant_id": "tenant-a", "currency": 1},
        {"tenant_id": "tenant-a", "currency": ""},
        {"tenant_id": "tenant-a", "currency": "USD", "now": datetime(2026, 1, 1)},
        {"tenant_id": "tenant-a", "currency": "USD", "operation": 1},
        {"tenant_id": "tenant-a", "currency": "USD", "operation": " "},
        {"tenant_id": "tenant-a", "currency": "USD", "metadata": []},
    ]
    for kwargs in calls:
        with pytest.raises(ValueError):
            router.list_candidates(**kwargs)

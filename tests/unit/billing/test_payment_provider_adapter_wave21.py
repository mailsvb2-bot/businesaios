from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from billing.commercial_cycle_contract import (
    CommercialCollectionAttempt,
    CommercialCollectionResult,
)
from billing.payment_provider_adapter import RoutingPaymentProviderAdapter
from billing.payment_provider_capability import PaymentProviderCapabilities
from billing.payment_provider_contract import PaymentCustomerProfile
from billing.payment_provider_health_registry import PaymentProviderHealthRegistry
from billing.payment_provider_registry import (
    PaymentProviderRegistration,
    PaymentProviderRegistry,
)
from billing.payment_provider_router import PaymentProviderRouter

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _Provider:
    def __init__(self, name: str) -> None:
        self.name = name
        self.ensure_calls = 0
        self.collect_calls = 0
        self.refund_calls = 0
        self.ensure_value = PaymentCustomerProfile(
            tenant_id="tenant-a",
            provider_customer_id=f"{name}:customer",
            default_currency="USD",
        )
        self.collect_value = CommercialCollectionResult(
            invoice_id="invoice-1",
            tenant_id="tenant-a",
            provider_name=name,
            successful=True,
            external_reference=f"{name}-charge",
            processed_at=NOW,
        )
        self.refund_value = {"provider_name": name, "refund_id": f"{name}-refund"}
        self.ensure_error: Exception | None = None
        self.collect_error: Exception | None = None
        self.refund_error: Exception | None = None

    def provider_name(self) -> str:
        return self.name

    def ensure_customer(self, **kwargs):
        self.ensure_calls += 1
        if self.ensure_error is not None:
            raise self.ensure_error
        return self.ensure_value

    def collect(self, attempt):
        self.collect_calls += 1
        if self.collect_error is not None:
            raise self.collect_error
        return self.collect_value

    def refund(self, **kwargs):
        self.refund_calls += 1
        if self.refund_error is not None:
            raise self.refund_error
        return self.refund_value


class _FaultyControlRouter(PaymentProviderRouter):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.fail_success = False
        self.fail_failure = False

    def mark_provider_success(self, provider_name: str) -> None:
        if self.fail_success:
            raise RuntimeError("metrics down")
        super().mark_provider_success(provider_name)

    def mark_provider_failure(self, provider_name: str, **kwargs) -> None:
        if self.fail_failure:
            raise RuntimeError("health down")
        super().mark_provider_failure(provider_name, **kwargs)


def _registration(provider: _Provider, *, priority: int, strict: bool = False):
    return PaymentProviderRegistration(
        provider_name=provider.name,
        provider=provider,
        currencies=("USD",),
        priority=priority,
        tenant_allowlist=("tenant-a",),
        capabilities=PaymentProviderCapabilities(
            operations=("ensure_customer", "collect", "refund"),
            strict_affinity_for_refund=strict,
        ),
        backend_key=f"{provider.name}-backend",
    )


def _system(*, faulty_router: bool = False):
    alpha = _Provider("alpha")
    beta = _Provider("beta")
    registry = PaymentProviderRegistry(
        (_registration(alpha, priority=10), _registration(beta, priority=20))
    )
    health = PaymentProviderHealthRegistry()
    router_cls = _FaultyControlRouter if faulty_router else PaymentProviderRouter
    router = router_cls(registry=registry, health_registry=health)
    return alpha, beta, registry, router, RoutingPaymentProviderAdapter(router=router, registry=registry)


def _attempt(**changes):
    values = {
        "invoice_id": "invoice-1",
        "tenant_id": "tenant-a",
        "amount_minor": 100,
        "currency": "USD",
        "provider_name": "routed",
        "idempotency_key": "invoice-1:1",
        "scheduled_at": NOW,
        "metadata": {},
    }
    values.update(changes)
    return CommercialCollectionAttempt(**values)


def test_constructor_provider_name_and_metadata_validation() -> None:
    alpha, beta, registry, router, adapter = _system()
    assert adapter.provider_name() == "routed"
    with pytest.raises(ValueError):
        RoutingPaymentProviderAdapter(router=object(), registry=registry)
    with pytest.raises(ValueError):
        RoutingPaymentProviderAdapter(router=router, registry=object())
    for metadata in ([], "bad"):
        with pytest.raises(ValueError, match="metadata must be a mapping"):
            adapter.ensure_customer(tenant_id="tenant-a", metadata=metadata)
    with pytest.raises(ValueError, match="tenant_id must be a string"):
        adapter.ensure_customer(tenant_id=1, metadata={"currency": "USD"})
    with pytest.raises(ValueError, match="email must be a string"):
        adapter.ensure_customer(tenant_id="tenant-a", email=1, metadata={"currency": "USD"})
    for currency in (None, 1, " "):
        with pytest.raises(ValueError, match="metadata.currency"):
            adapter.ensure_customer(tenant_id="tenant-a", metadata={"currency": currency})


def test_ensure_customer_success_binding_and_no_post_call_failover() -> None:
    alpha, beta, registry, router, adapter = _system()
    profile = adapter.ensure_customer(
        tenant_id="tenant-a", email="a@example.test", metadata={"currency": "usd"}
    )
    assert profile.provider_customer_id == "alpha:customer"
    assert profile.metadata["routed_provider"] == "alpha"
    assert alpha.ensure_calls == 1 and beta.ensure_calls == 0

    alpha.ensure_error = TimeoutError("response lost")
    with pytest.raises(RuntimeError, match="failed ensure_customer"):
        adapter.ensure_customer(tenant_id="tenant-a", metadata={"currency": "USD"})
    assert alpha.ensure_calls == 2 and beta.ensure_calls == 0


def test_ensure_customer_rejects_invalid_results_without_failover() -> None:
    cases = [
        object(),
        PaymentCustomerProfile("tenant-b", "alpha:c", "USD"),
        PaymentCustomerProfile("tenant-a", "alpha:c", "EUR"),
        PaymentCustomerProfile("tenant-a", "", "USD"),
    ]
    for value in cases:
        alpha, beta, registry, router, adapter = _system()
        alpha.ensure_value = value
        with pytest.raises(RuntimeError, match="invalid customer profile"):
            adapter.ensure_customer(tenant_id="tenant-a", metadata={"currency": "USD"})
        assert alpha.ensure_calls == 1 and beta.ensure_calls == 0


def test_collect_success_and_ambiguous_failure_never_reaches_second_provider() -> None:
    alpha, beta, registry, router, adapter = _system()
    result = adapter.collect(_attempt())
    assert result.external_reference == "alpha-charge"
    assert result.metadata["provider_backend_key"] == "alpha-backend"
    assert alpha.collect_calls == 1 and beta.collect_calls == 0

    alpha.collect_error = TimeoutError("charge committed, response lost")
    with pytest.raises(RuntimeError, match="failed collection"):
        adapter.collect(_attempt())
    assert alpha.collect_calls == 2 and beta.collect_calls == 0
    with pytest.raises(ValueError, match="attempt must"):
        adapter.collect(object())


def test_collect_rejects_malformed_or_cross_bound_results_without_failover() -> None:
    cases = [
        object(),
        CommercialCollectionResult(
            "other", "tenant-a", "alpha", True, external_reference="x", processed_at=NOW
        ),
        CommercialCollectionResult(
            "invoice-1", "tenant-b", "alpha", True, external_reference="x", processed_at=NOW
        ),
        CommercialCollectionResult(
            "invoice-1", "tenant-a", "beta", True, external_reference="x", processed_at=NOW
        ),
        CommercialCollectionResult(
            "invoice-1", "tenant-a", "alpha", False, processed_at=NOW
        ),
    ]
    for value in cases:
        alpha, beta, registry, router, adapter = _system()
        alpha.collect_value = value
        with pytest.raises(RuntimeError, match="invalid collection result"):
            adapter.collect(_attempt())
        assert alpha.collect_calls == 1 and beta.collect_calls == 0


def test_pre_call_health_filter_can_select_second_provider() -> None:
    alpha, beta, registry, router, adapter = _system()
    router.mark_provider_failure("alpha", reason="down", cooldown_seconds=60, now=NOW)
    result = adapter.collect(_attempt())
    assert result.provider_name == "beta"
    assert alpha.collect_calls == 0 and beta.collect_calls == 1


def test_refund_success_binding_and_no_post_call_failover() -> None:
    alpha, beta, registry, router, adapter = _system()
    alpha.refund_value = {
        "provider_name": "alpha",
        "invoice_id": "invoice-1",
        "tenant_id": "tenant-a",
        "currency": "USD",
        "amount_minor": 100,
    }
    payload = adapter.refund(
        invoice_id="invoice-1",
        tenant_id="tenant-a",
        amount_minor=100,
        currency="usd",
        reason="duplicate",
    )
    assert payload["provider_backend_key"] == "alpha-backend"
    assert alpha.refund_calls == 1 and beta.refund_calls == 0

    alpha.refund_error = TimeoutError("refund committed, response lost")
    with pytest.raises(RuntimeError, match="failed refund"):
        adapter.refund(
            invoice_id="invoice-1",
            tenant_id="tenant-a",
            amount_minor=100,
            currency="USD",
            reason="duplicate",
        )
    assert alpha.refund_calls == 2 and beta.refund_calls == 0


def test_refund_rejects_invalid_inputs_and_results() -> None:
    alpha, beta, registry, router, adapter = _system()
    invalid_calls = [
        {"invoice_id": "", "tenant_id": "tenant-a", "amount_minor": 1, "currency": "USD", "reason": "x"},
        {"invoice_id": "i", "tenant_id": 1, "amount_minor": 1, "currency": "USD", "reason": "x"},
        {"invoice_id": "i", "tenant_id": "tenant-a", "amount_minor": True, "currency": "USD", "reason": "x"},
        {"invoice_id": "i", "tenant_id": "tenant-a", "amount_minor": 0, "currency": "USD", "reason": "x"},
        {"invoice_id": "i", "tenant_id": "tenant-a", "amount_minor": 1, "currency": 1, "reason": "x"},
        {"invoice_id": "i", "tenant_id": "tenant-a", "amount_minor": 1, "currency": "", "reason": "x"},
        {"invoice_id": "i", "tenant_id": "tenant-a", "amount_minor": 1, "currency": "USD", "reason": 1},
        {"invoice_id": "i", "tenant_id": "tenant-a", "amount_minor": 1, "currency": "USD", "reason": ""},
        {"invoice_id": "i", "tenant_id": "tenant-a", "amount_minor": 1, "currency": "USD", "reason": "x", "metadata": []},
    ]
    for kwargs in invalid_calls:
        with pytest.raises(ValueError):
            adapter.refund(**kwargs)

    invalid_results = [
        [],
        {"provider_name": "beta"},
        {"provider_name": "alpha", "invoice_id": "other"},
        {"provider_name": "alpha", "tenant_id": "other"},
        {"provider_name": "alpha", "currency": "EUR"},
        {"provider_name": "alpha", "amount_minor": True},
        {"provider_name": "alpha", "amount_minor": 101},
    ]
    for value in invalid_results:
        alpha, beta, registry, router, adapter = _system()
        alpha.refund_value = value
        with pytest.raises(RuntimeError, match="invalid refund result"):
            adapter.refund(
                invoice_id="invoice-1",
                tenant_id="tenant-a",
                amount_minor=100,
                currency="USD",
                reason="duplicate",
            )
        assert alpha.refund_calls == 1 and beta.refund_calls == 0


def test_preferred_provider_and_strict_affinity_are_fail_closed() -> None:
    alpha, beta, registry, router, adapter = _system()
    result = adapter.collect(_attempt(metadata={"preferred_provider": "beta"}))
    assert result.provider_name == "beta"
    assert beta.collect_calls == 1
    with pytest.raises(LookupError, match="unknown provider"):
        adapter.collect(_attempt(metadata={"preferred_provider": "missing"}))
    with pytest.raises(LookupError, match="unknown provider"):
        adapter.collect(_attempt(metadata={"provider_customer_id": "missing:cust"}))

    alpha.refund_value = {"provider_name": "alpha"}
    payload = adapter.refund(
        invoice_id="invoice-1",
        tenant_id="tenant-a",
        amount_minor=100,
        currency="USD",
        reason="duplicate",
        metadata={"provider_customer_id": "alpha:cust"},
    )
    assert payload["provider_name"] == "alpha"
    with pytest.raises(LookupError):
        adapter.refund(
            invoice_id="invoice-1",
            tenant_id="tenant-a",
            amount_minor=100,
            currency="USD",
            reason="duplicate",
            metadata={"strict_provider_affinity": True},
        )


def test_affinity_and_provider_helpers_reject_malformed_values() -> None:
    alpha, beta, registry, router, adapter = _system()
    assert adapter._has_strict_affinity({}, operation="collect") is False
    assert adapter._has_strict_affinity({"preferred_provider": "alpha"}, operation="refund") is True
    assert adapter._has_strict_affinity({"provider_name_hint": "alpha"}, operation="refund") is True
    assert adapter._has_strict_affinity({"provider_customer_id": "alpha:c"}, operation="refund") is True
    assert adapter._has_strict_affinity({}, operation="refund") is False
    invalid = [
        ([], "refund"),
        ({}, 1),
        ({"strict_provider_affinity": "yes"}, "refund"),
        ({"preferred_provider": 1}, "refund"),
        ({"provider_name_hint": 1}, "refund"),
        ({"provider_customer_id": 1}, "refund"),
    ]
    for metadata, operation in invalid:
        with pytest.raises(ValueError):
            adapter._has_strict_affinity(metadata, operation=operation)
    with pytest.raises(ValueError):
        adapter._extract_preferred_provider([])
    with pytest.raises(ValueError):
        adapter._extract_preferred_provider({"preferred_provider": 1})
    with pytest.raises(ValueError):
        adapter._extract_preferred_provider({"provider_customer_id": 1})
    assert adapter._extract_preferred_provider({"provider_customer_id": "plain"}) is None
    assert adapter._ordered_providers(
        tenant_id="tenant-a", currency="USD", operation="collect", metadata={}
    )[0] is alpha
    with pytest.raises(ValueError):
        adapter._ordered_providers(
            tenant_id="tenant-a", currency="USD", operation="collect", metadata=[]
        )
    with pytest.raises(ValueError):
        adapter._provider_name(object())
    with pytest.raises(ValueError):
        adapter._provider_name(SimpleNamespace(provider_name=lambda: 1))
    with pytest.raises(ValueError):
        adapter._provider_name(SimpleNamespace(provider_name=lambda: ""))


def test_control_plane_failures_never_change_external_outcome() -> None:
    alpha, beta, registry, router, adapter = _system(faulty_router=True)
    router.fail_success = True
    result = adapter.collect(_attempt())
    assert result.successful is True and alpha.collect_calls == 1 and beta.collect_calls == 0

    alpha.collect_error = TimeoutError("lost")
    router.fail_failure = True
    with pytest.raises(RuntimeError, match="failed collection"):
        adapter.collect(_attempt())
    assert alpha.collect_calls == 2 and beta.collect_calls == 0


def test_missing_candidates_and_impossible_affinity_mismatch_fail_closed(monkeypatch) -> None:
    alpha, beta, registry, router, adapter = _system()
    empty_registry = PaymentProviderRegistry()
    empty_router = PaymentProviderRouter(registry=empty_registry)
    empty_adapter = RoutingPaymentProviderAdapter(router=empty_router, registry=empty_registry)
    with pytest.raises(LookupError, match="ensure_customer"):
        empty_adapter.ensure_customer(tenant_id="tenant-a", metadata={"currency": "USD"})

    monkeypatch.setattr(adapter, "_ordered_providers", lambda **kwargs: (beta,))
    with pytest.raises(LookupError, match="preferred refund provider"):
        adapter.refund(
            invoice_id="invoice-1",
            tenant_id="tenant-a",
            amount_minor=100,
            currency="USD",
            reason="duplicate",
            metadata={"preferred_provider": "alpha"},
        )


def test_blank_affinity_tokens_do_not_create_affinity() -> None:
    alpha, beta, registry, router, adapter = _system()
    assert adapter._extract_preferred_provider({"preferred_provider": " "}) is None
    assert adapter._extract_preferred_provider({"provider_customer_id": ":customer"}) is None

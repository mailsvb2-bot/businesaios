from __future__ import annotations

from datetime import UTC, datetime

import pytest

from billing.commercial_cycle_contract import CommercialCollectionAttempt, CommercialCollectionResult
from billing.dispute_orchestrator import DisputeOrchestrator, InMemoryDisputeStore, SqliteDisputeStore
from billing.payment_provider_adapter import RoutingPaymentProviderAdapter
from billing.payment_provider_capability import PaymentProviderCapabilities
from billing.payment_provider_contract import PaymentCustomerProfile, PaymentProviderContract
from billing.payment_provider_health_registry import PaymentProviderHealthRegistry
from billing.payment_provider_registry import PaymentProviderRegistration, PaymentProviderRegistry
from billing.payment_provider_router import PaymentProviderRouter
from billing.tax_policy_bridge import BillingTaxCountryPolicy, BillingTaxPolicyBridge, BillingTaxPolicyRegistry
from runtime.monetization import MonetizationService, TaxContext


class _Provider(PaymentProviderContract):
    def __init__(self, name: str, *, fail_collect: bool = False, fail_refund: bool = False, fail_customer: bool = False) -> None:
        self._name = name
        self._fail_collect = fail_collect
        self._fail_refund = fail_refund
        self._fail_customer = fail_customer

    def provider_name(self) -> str:
        return self._name

    def ensure_customer(self, *, tenant_id: str, email: str | None = None, metadata=None):
        if self._fail_customer:
            raise RuntimeError('customer boom')
        currency = dict(metadata or {}).get('currency', 'USD')
        return PaymentCustomerProfile(tenant_id=tenant_id, provider_customer_id=f'{self._name}:{email or "anon"}', default_currency=currency)

    def collect(self, attempt):
        attempt.validate()
        if self._fail_collect:
            raise RuntimeError('collect boom')
        return CommercialCollectionResult(
            invoice_id=attempt.invoice_id,
            tenant_id=attempt.tenant_id,
            provider_name=self._name,
            successful=True,
            external_reference=f'{self._name}:{attempt.idempotency_key}',
            metadata={'echo_provider': self._name},
        )

    def refund(self, *, invoice_id: str, tenant_id: str, amount_minor: int, currency: str, reason: str, metadata=None):
        if self._fail_refund:
            raise RuntimeError('refund boom')
        return {'external_reference': f'{self._name}:{invoice_id}:refund', 'provider_name': self._name, 'currency': currency, 'reason': reason}


def test_routing_payment_provider_adapter_routes_collection_and_customer_by_currency() -> None:
    registry = PaymentProviderRegistry([
        PaymentProviderRegistration(provider_name='eurpay', provider=_Provider('eurpay'), currencies=('EUR',), priority=10),
        PaymentProviderRegistration(provider_name='usdpay', provider=_Provider('usdpay'), currencies=('USD',), priority=10),
    ])
    adapter = RoutingPaymentProviderAdapter(router=PaymentProviderRouter(registry=registry, health_registry=PaymentProviderHealthRegistry()), registry=registry)

    customer = adapter.ensure_customer(tenant_id='tenant-a', email='x@example.com', metadata={'currency': 'eur'})
    assert customer.metadata['routed_provider'] == 'eurpay'
    assert customer.default_currency == 'EUR'

    result = adapter.collect(CommercialCollectionAttempt(invoice_id='inv-1', tenant_id='tenant-a', amount_minor=100, currency='EUR', provider_name='routed', idempotency_key='idem-1'))
    assert result.provider_name == 'eurpay'
    assert result.metadata['routed_provider'] == 'eurpay'

    refund_payload = adapter.refund(invoice_id='inv-1', tenant_id='tenant-a', amount_minor=100, currency='USD', reason='goodwill')
    assert refund_payload['provider_name'] == 'usdpay'


def test_dispute_orchestrator_is_idempotent_and_sqlite_persistent(tmp_path) -> None:
    store = SqliteDisputeStore(sqlite_path=str(tmp_path / 'disputes.sqlite3'))
    orchestrator = DisputeOrchestrator(store=store)

    opened = orchestrator.open_case(
        tenant_id='tenant-a',
        invoice_id='inv-1',
        payload={'duplicate_flag': True, 'attribution_mismatch': True},
        idempotency_key='dsp-1',
        opened_at=datetime(2026, 4, 10, 10, 0, tzinfo=UTC),
    )
    replayed = orchestrator.open_case(
        tenant_id='tenant-a',
        invoice_id='inv-1',
        payload={'duplicate_flag': True, 'attribution_mismatch': True},
        idempotency_key='dsp-1',
        opened_at=datetime(2026, 4, 10, 10, 0, tzinfo=UTC),
    )
    assert replayed == opened
    assert store.get_by_idempotency(tenant_id='tenant-a', invoice_id='inv-1', idempotency_key='dsp-1') == opened

    resolved = orchestrator.resolve_case(case=opened, resolution='merchant_won')
    assert resolved.status == 'resolved'
    assert store.get(tenant_id='tenant-a', case_id=opened.case_id) == resolved


def test_dispute_store_rejects_idempotency_collision() -> None:
    store = InMemoryDisputeStore()
    orchestrator = DisputeOrchestrator(store=store)
    original = orchestrator.open_case(tenant_id='tenant-a', invoice_id='inv-1', payload={'duplicate_flag': True}, idempotency_key='same')
    with pytest.raises(ValueError):
        store.save(
            type(original)(
                tenant_id='tenant-a',
                invoice_id='inv-1',
                case_id='manual-collision',
                classification=original.classification,
                status='open',
                idempotency_key='same',
                opened_at=original.opened_at,
                metadata={'different': True},
            ),
            idempotency_key='same',
        )


def test_tax_policy_bridge_fail_closed_on_invalid_context() -> None:
    bridge = BillingTaxPolicyBridge()
    with pytest.raises(ValueError):
        bridge.resolve(service=MonetizationService(), subtotal_minor=-1, context=TaxContext(country_code='NL'))
    with pytest.raises(ValueError):
        bridge.resolve(service=MonetizationService(), subtotal_minor=100, context=TaxContext(country_code=''))


def test_routing_payment_provider_adapter_skips_known_unhealthy_provider_before_dispatch() -> None:
    health = PaymentProviderHealthRegistry()
    primary = _Provider('primary', fail_collect=True, fail_refund=True, fail_customer=True)
    secondary = _Provider('secondary')
    registry = PaymentProviderRegistry([
        PaymentProviderRegistration(provider_name='primary', provider=primary, currencies=('USD',), priority=1),
        PaymentProviderRegistration(provider_name='secondary', provider=secondary, currencies=('USD',), priority=2),
    ])
    observed_at = datetime(2026, 4, 10, 10, 0, tzinfo=UTC)
    health.mark_failure('primary', reason='preflight_unavailable', cooldown_seconds=300, now=observed_at)
    router = PaymentProviderRouter(registry=registry, health_registry=health)
    adapter = RoutingPaymentProviderAdapter(router=router, registry=registry)

    customer = adapter.ensure_customer(tenant_id='tenant-a', email='x@example.com', metadata={'currency': 'USD'})
    assert customer.metadata['routed_provider'] == 'secondary'
    assert health.get('primary').healthy is False

    result = adapter.collect(CommercialCollectionAttempt(invoice_id='inv-2', tenant_id='tenant-a', amount_minor=150, currency='USD', provider_name='routed', idempotency_key='idem-2', scheduled_at=observed_at))
    assert result.provider_name == 'secondary'

    refund_payload = adapter.refund(invoice_id='inv-2', tenant_id='tenant-a', amount_minor=150, currency='USD', reason='goodwill')
    assert refund_payload['provider_name'] == 'secondary'


def test_dispute_orchestrator_prevents_double_resolution_and_supports_escalation() -> None:
    orchestrator = DisputeOrchestrator(store=InMemoryDisputeStore())
    opened = orchestrator.open_case(tenant_id='tenant-a', invoice_id='inv-9', payload={'duplicate_flag': True})
    escalated = orchestrator.escalate_case(case=opened, resolution='needs_network_review')
    assert escalated.status == 'escalated'
    with pytest.raises(ValueError):
        orchestrator.resolve_case(case=escalated, resolution='merchant_won')


def test_routing_payment_provider_adapter_prefers_provider_affinity_before_fallback() -> None:
    health = PaymentProviderHealthRegistry()
    registry = PaymentProviderRegistry([
        PaymentProviderRegistration(provider_name='primary', provider=_Provider('primary'), currencies=('USD',), priority=1),
        PaymentProviderRegistration(provider_name='secondary', provider=_Provider('secondary'), currencies=('USD',), priority=2),
    ])
    router = PaymentProviderRouter(registry=registry, health_registry=health)
    adapter = RoutingPaymentProviderAdapter(router=router, registry=registry)

    result = adapter.collect(
        CommercialCollectionAttempt(
            invoice_id='inv-affinity',
            tenant_id='tenant-a',
            amount_minor=100,
            currency='USD',
            provider_name='routed',
            idempotency_key='idem-affinity',
            metadata={'provider_customer_id': 'secondary:cust-1'},
        )
    )
    assert result.provider_name == 'secondary'
    assert result.metadata['routed_provider'] == 'secondary'


def test_tax_policy_bridge_registry_is_fail_closed_for_unknown_country_and_b2b_tax_id() -> None:
    bridge = BillingTaxPolicyBridge(
        registry=BillingTaxPolicyRegistry(policies=[BillingTaxCountryPolicy(country_code='NL', b2c_tax_rate_bps=2100, b2b_reverse_charge=True)])
    )
    assert bridge.resolve(service=MonetizationService(), subtotal_minor=1000, context=TaxContext(country_code='NL')).tax_minor == 210
    assert bridge.resolve(service=MonetizationService(), subtotal_minor=1000, context=TaxContext(country_code='NL', business_customer=True, tax_id='NL123')).tax_minor == 0
    with pytest.raises(LookupError):
        bridge.resolve(service=MonetizationService(), subtotal_minor=1000, context=TaxContext(country_code='DE'))
    with pytest.raises(ValueError):
        bridge.resolve(service=MonetizationService(), subtotal_minor=1000, context=TaxContext(country_code='NL', business_customer=True))

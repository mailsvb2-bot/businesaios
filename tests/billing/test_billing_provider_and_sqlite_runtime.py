from __future__ import annotations

from dataclasses import dataclass
import pytest
from datetime import datetime, timezone
from pathlib import Path

from billing.commercial_cycle_contract import CommercialCollectionResult, utc_now
from billing.invoice_lifecycle import CommercialInvoiceEnvelope, InvoiceLifecycleService
from billing.ledger_event import LedgerEntry, LedgerPosting
from billing.payment_collection import PaymentCollectionOrchestrator
from billing.payment_provider_contract import PaymentCustomerProfile, PaymentProviderContract
from billing.payment_provider_health_registry import PaymentProviderHealthRegistry
from billing.payment_provider_registry import PaymentProviderRegistration, PaymentProviderRegistry
from billing.payment_provider_router import PaymentProviderRouter
from billing.sqlite_store import SqliteCollectionResultStore, SqliteLedgerStore


@dataclass(frozen=True)
class _Provider(PaymentProviderContract):
    name: str

    def provider_name(self) -> str:
        return self.name

    def ensure_customer(self, *, tenant_id: str, email: str | None = None, metadata=None):
        return PaymentCustomerProfile(tenant_id=tenant_id, provider_customer_id=f'{self.name}:{tenant_id}')

    def collect(self, attempt):
        return CommercialCollectionResult(
            invoice_id=attempt.invoice_id,
            tenant_id=attempt.tenant_id,
            provider_name=self.provider_name(),
            successful=True,
            external_reference=f'{self.name}:{attempt.idempotency_key}',
        )

    def refund(self, *, invoice_id: str, tenant_id: str, amount_minor: int, currency: str, reason: str, metadata=None):
        return {'status': 'processed', 'provider': self.name}


def test_payment_provider_router_prefers_healthy_matching_currency_provider() -> None:
    registry = PaymentProviderRegistry(
        registrations=(
            PaymentProviderRegistration(provider_name='primary', provider=_Provider('primary'), currencies=('USD',), priority=10),
            PaymentProviderRegistration(provider_name='fallback', provider=_Provider('fallback'), currencies=('USD', 'EUR'), priority=20),
        )
    )
    health = PaymentProviderHealthRegistry()
    health.mark_failure('primary', reason='gateway timeout', cooldown_seconds=300, now=datetime(2026, 4, 9, tzinfo=timezone.utc))
    router = PaymentProviderRouter(registry=registry, health_registry=health)
    selection = router.select(tenant_id='tenant-a', currency='USD', now=datetime(2026, 4, 9, 0, 1, tzinfo=timezone.utc))
    assert selection.provider_name == 'fallback'


def test_payment_provider_router_respects_tenant_allowlist() -> None:
    registry = PaymentProviderRegistry(
        registrations=(
            PaymentProviderRegistration(provider_name='eu-only', provider=_Provider('eu-only'), currencies=('EUR',), tenant_allowlist=('tenant-eu',), priority=5),
            PaymentProviderRegistration(provider_name='default', provider=_Provider('default'), currencies=('EUR',), priority=10),
        )
    )
    router = PaymentProviderRouter(registry=registry)
    assert router.select(tenant_id='tenant-eu', currency='EUR').provider_name == 'eu-only'
    assert router.select(tenant_id='tenant-us', currency='EUR').provider_name == 'default'


def test_sqlite_collection_store_persists_idempotent_results(tmp_path: Path) -> None:
    store = SqliteCollectionResultStore(sqlite_path=str(tmp_path / 'billing.sqlite3'))
    invoice = InvoiceLifecycleService().issue(
        CommercialInvoiceEnvelope(invoice_id='inv-1', tenant_id='tenant-a', currency='USD', subtotal_minor=1000, tax_minor=200, total_minor=1200)
    )
    orchestrator = PaymentCollectionOrchestrator(provider=_Provider('sqlite-provider'), result_store=store)
    first_invoice, first_result = orchestrator.collect(invoice=invoice, idempotency_key='idem-1')
    replayed_invoice, replayed_result = orchestrator.collect(invoice=invoice, idempotency_key='idem-1')
    assert first_result == replayed_result
    assert first_invoice.paid_minor == 1200
    assert replayed_invoice.paid_minor == 1200
    reloaded = SqliteCollectionResultStore(sqlite_path=str(tmp_path / 'billing.sqlite3'))
    assert len(reloaded.list_for_invoice('inv-1', tenant_id='tenant-a')) == 1
    assert reloaded.get_by_idempotency(tenant_id='tenant-a', invoice_id='inv-1', idempotency_key='idem-1') == first_result


def test_sqlite_ledger_store_persists_balanced_postings(tmp_path: Path) -> None:
    ledger = SqliteLedgerStore(sqlite_path=str(tmp_path / 'ledger.sqlite3'))
    posting = LedgerPosting(
        posting_id='post-1',
        tenant_id='tenant-a',
        reference_type='invoice',
        reference_id='inv-9',
        entries=(
            LedgerEntry(tenant_id='tenant-a', entry_id='e1', account_code='billing.accounts.ar', side='debit', amount_minor=700, currency='USD', reference_type='invoice', reference_id='inv-9'),
            LedgerEntry(tenant_id='tenant-a', entry_id='e2', account_code='billing.accounts.revenue', side='credit', amount_minor=700, currency='USD', reference_type='invoice', reference_id='inv-9'),
        ),
    )
    ledger.append(posting)
    reloaded = SqliteLedgerStore(sqlite_path=str(tmp_path / 'ledger.sqlite3'))
    postings = reloaded.list_postings(tenant_id='tenant-a')
    assert len(postings) == 1
    assert postings[0].posting_id == 'post-1'
    assert reloaded.total_for_account(tenant_id='tenant-a', account_code='billing.accounts.revenue', side='credit') == 700



def test_payment_provider_health_without_cooldown_is_not_available_when_unhealthy() -> None:
    health = PaymentProviderHealthRegistry()
    health._statuses['broken'] = __import__('billing.payment_provider_health_registry', fromlist=['ProviderHealthStatus']).ProviderHealthStatus(
        provider_name='broken', healthy=False, cooldown_until=None, failure_count=3, last_failure_reason='downstream hard fail'
    )
    assert health.is_available('broken', now=datetime(2026, 4, 9, tzinfo=timezone.utc)) is False


def test_router_prefers_lower_failure_count_when_priority_ties() -> None:
    registry = PaymentProviderRegistry(
        registrations=(
            PaymentProviderRegistration(provider_name='stable', provider=_Provider('stable'), currencies=('USD',), priority=10),
            PaymentProviderRegistration(provider_name='flaky', provider=_Provider('flaky'), currencies=('USD',), priority=10),
        )
    )
    health = PaymentProviderHealthRegistry()
    health.mark_failure('flaky', reason='timeout', cooldown_seconds=0, now=datetime(2026, 4, 9, tzinfo=timezone.utc))
    router = PaymentProviderRouter(registry=registry, health_registry=health)
    selection = router.select(tenant_id='tenant-a', currency='USD', now=datetime(2026, 4, 9, tzinfo=timezone.utc))
    assert selection.provider_name == 'stable'
    assert selection.metadata['failure_count'] == 0


def test_sqlite_collection_store_rejects_idempotent_collision_after_reload(tmp_path: Path) -> None:
    store = SqliteCollectionResultStore(sqlite_path=str(tmp_path / 'billing.sqlite3'))
    ok = CommercialCollectionResult(
        invoice_id='inv-collide', tenant_id='tenant-a', provider_name='provider', successful=True, external_reference='ok:1'
    )
    store.append(ok, idempotency_key='same')
    conflicting = CommercialCollectionResult(
        invoice_id='inv-collide', tenant_id='tenant-a', provider_name='provider', successful=True, external_reference='ok:2'
    )
    try:
        SqliteCollectionResultStore(sqlite_path=str(tmp_path / 'billing.sqlite3')).append(conflicting, idempotency_key='same')
    except ValueError:
        pass
    else:
        raise AssertionError('expected sqlite idempotency collision to fail')


def test_sqlite_ledger_store_rejects_posting_id_collision_with_different_payload(tmp_path: Path) -> None:
    ledger = SqliteLedgerStore(sqlite_path=str(tmp_path / 'ledger.sqlite3'))
    posting = LedgerPosting(
        posting_id='dup-post', tenant_id='tenant-a', reference_type='invoice', reference_id='inv-1',
        entries=(
            LedgerEntry(tenant_id='tenant-a', entry_id='e1', account_code='billing.accounts.ar', side='debit', amount_minor=700, currency='USD', reference_type='invoice', reference_id='inv-1'),
            LedgerEntry(tenant_id='tenant-a', entry_id='e2', account_code='billing.accounts.revenue', side='credit', amount_minor=700, currency='USD', reference_type='invoice', reference_id='inv-1'),
        ),
    )
    ledger.append(posting)
    conflicting = LedgerPosting(
        posting_id='dup-post', tenant_id='tenant-a', reference_type='invoice', reference_id='inv-1',
        entries=(
            LedgerEntry(tenant_id='tenant-a', entry_id='e3', account_code='billing.accounts.ar', side='debit', amount_minor=800, currency='USD', reference_type='invoice', reference_id='inv-1'),
            LedgerEntry(tenant_id='tenant-a', entry_id='e4', account_code='billing.accounts.revenue', side='credit', amount_minor=800, currency='USD', reference_type='invoice', reference_id='inv-1'),
        ),
    )
    try:
        ledger.append(conflicting)
    except ValueError:
        pass
    else:
        raise AssertionError('expected sqlite posting collision to fail')



def test_provider_registry_normalizes_name_case_and_currency() -> None:
    provider = _Provider('Stripe')
    registry = PaymentProviderRegistry()
    registry.register(
        PaymentProviderRegistration(
            provider_name='stripe',
            provider=provider,
            currencies=('usd', 'EUR'),
            tenant_allowlist=('tenant-a',),
        )
    )
    loaded = registry.get('STRIPE')
    assert loaded.provider_name == 'stripe'
    assert loaded.currencies == ('EUR', 'USD')
    assert loaded.supports(tenant_id='tenant-a', currency='usd') is True


def test_provider_health_negative_cooldown_rejected() -> None:
    registry = PaymentProviderHealthRegistry()
    with pytest.raises(ValueError):
        registry.mark_failure('stripe', reason='boom', cooldown_seconds=-1, now=utc_now())

from __future__ import annotations

from dataclasses import dataclass, replace
import pytest
from datetime import datetime, timedelta, timezone

from billing.credit_balance import InMemoryCreditBalanceStore
from billing.commercial_cycle_contract import DunningAction, SubscriptionLifecycleStatus, utc_now
from billing.dunning_orchestrator import DunningOrchestrator, InMemoryDunningScheduleStore
from billing.invoice_lifecycle import CommercialInvoiceEnvelope, InvoiceLifecycleService
from billing.ledger_event import LedgerEntry, LedgerPosting
from billing.ledger_store import InMemoryLedgerStore
from billing.payment_collection import InMemoryCollectionResultStore, PaymentCollectionOrchestrator
from billing.payment_provider_contract import PaymentCustomerProfile, PaymentProviderContract
from billing.plan_change_policy import PlanChangePolicy, PlanChangeQuote
from billing.plan_contract import BillingPlanSpec, PlanRateCardItem
from billing.reconciliation_service import BillingReconciliationService
from billing.spend_guard import SpendGuard, SpendLimitPolicy
from billing.subscription_lifecycle import SubscriptionLifecycleService
from billing.tax_policy_bridge import BillingTaxPolicyBridge
from billing.usage_meter import UsageRecord
from billing.usage_rollup import UsageRollupBuilder
from runtime.monetization import MonetizationService, TaxContext
from tenancy.tenant_contract import TenantPlan


@dataclass(frozen=True)
class _Provider(PaymentProviderContract):
    def provider_name(self) -> str:
        return 'dummy'

    def ensure_customer(self, *, tenant_id: str, email: str | None = None, metadata=None):
        raise NotImplementedError

    def collect(self, attempt):
        from billing.commercial_cycle_contract import CommercialCollectionResult

        return CommercialCollectionResult(
            invoice_id=attempt.invoice_id,
            tenant_id=attempt.tenant_id,
            provider_name=self.provider_name(),
            successful=True,
            external_reference=f'ok:{attempt.idempotency_key}',
        )

    def refund(self, *, invoice_id: str, tenant_id: str, amount_minor: int, currency: str, reason: str, metadata=None):
        return {'status': 'processed', 'invoice_id': invoice_id}


def _plan(plan_id: TenantPlan, amount: float, currency: str = 'USD') -> BillingPlanSpec:
    return BillingPlanSpec(
        plan_id=plan_id,
        display_name=plan_id.value.title(),
        metadata={'base_amount': amount, 'interval': 'monthly'},
        rate_card=(PlanRateCardItem(meter_key='connector_calls', unit_price=0.25, currency=currency, included_units=10),),
    )


def test_subscription_cycle_uses_calendar_months() -> None:
    svc = SubscriptionLifecycleService()
    started_at = datetime(2026, 1, 31, tzinfo=timezone.utc)
    envelope = svc.activate(tenant_id='tenant-a', subscription_id='sub-1', plan_id='growth', activated_at=started_at)
    assert envelope.cycle.end_at == datetime(2026, 2, 28, tzinfo=timezone.utc)


def test_invoice_lifecycle_guards_closed_state_and_remaining_minor() -> None:
    lifecycle = InvoiceLifecycleService()
    issued = lifecycle.issue(CommercialInvoiceEnvelope(invoice_id='inv-1', tenant_id='tenant-a', currency='USD', subtotal_minor=1000, tax_minor=200, total_minor=1200))
    partially_paid = lifecycle.record_payment(issued, amount_minor=200)
    assert partially_paid.remaining_minor == 1000
    paid = lifecycle.record_payment(partially_paid, amount_minor=1000)
    assert paid.remaining_minor == 0
    try:
        lifecycle.void(paid)
    except ValueError:
        pass
    else:
        raise AssertionError('expected void on paid invoice to fail')


def test_payment_collection_is_idempotent() -> None:
    invoice = InvoiceLifecycleService().issue(CommercialInvoiceEnvelope(invoice_id='inv-1', tenant_id='tenant-a', currency='USD', subtotal_minor=1000, tax_minor=200, total_minor=1200))
    store = InMemoryCollectionResultStore()
    orchestrator = PaymentCollectionOrchestrator(provider=_Provider(), result_store=store)
    paid_first, result_first = orchestrator.collect(invoice=invoice, idempotency_key='x-1')
    paid_second, result_second = orchestrator.collect(invoice=invoice, idempotency_key='x-1')
    assert result_first is result_second
    assert paid_first.paid_minor == 1200
    assert paid_second.paid_minor == 1200
    assert len(store.list_for_invoice('inv-1')) == 1


def test_ledger_store_is_idempotent_per_posting_id() -> None:
    ledger = InMemoryLedgerStore()
    posting = LedgerPosting(
        posting_id='p-1',
        tenant_id='tenant-a',
        reference_type='invoice',
        reference_id='inv-1',
        entries=(
            LedgerEntry(tenant_id='tenant-a', entry_id='1', account_code='billing.accounts.ar', side='debit', amount_minor=1200, currency='USD', reference_type='invoice', reference_id='inv-1'),
            LedgerEntry(tenant_id='tenant-a', entry_id='2', account_code='billing.accounts.revenue', side='credit', amount_minor=1200, currency='USD', reference_type='invoice', reference_id='inv-1'),
        ),
    )
    ledger.append(posting)
    ledger.append(posting)
    assert len(ledger.list_postings(tenant_id='tenant-a')) == 1


def test_spend_guard_remaining_minor_reflects_post_projection() -> None:
    ledger = InMemoryLedgerStore()
    posting = LedgerPosting(
        posting_id='p-1',
        tenant_id='tenant-a',
        reference_type='invoice',
        reference_id='inv-1',
        entries=(
            LedgerEntry(tenant_id='tenant-a', entry_id='1', account_code='billing.accounts.ar', side='debit', amount_minor=1000, currency='USD', reference_type='invoice', reference_id='inv-1'),
            LedgerEntry(tenant_id='tenant-a', entry_id='2', account_code='billing.accounts.revenue', side='credit', amount_minor=1000, currency='USD', reference_type='invoice', reference_id='inv-1'),
        ),
    )
    ledger.append(posting)
    verdict = SpendGuard(ledger_store=ledger).check(policy=SpendLimitPolicy(tenant_id='tenant-a', cycle_limit_minor=1500), pending_minor=200)
    assert verdict.remaining_minor == 300


def test_credit_balance_rejects_negative_adjustments() -> None:
    store = InMemoryCreditBalanceStore()
    try:
        store.add(tenant_id='tenant-a', currency='USD', amount_minor=-1)
    except ValueError:
        pass
    else:
        raise AssertionError('expected negative add to fail')


def test_dunning_open_run_is_idempotent_by_default() -> None:
    schedule_store = InMemoryDunningScheduleStore()
    orchestrator = DunningOrchestrator(store=schedule_store)
    first = orchestrator.open_run(tenant_id='tenant-a', invoice_id='inv-9', started_at=datetime(2026, 4, 1, tzinfo=timezone.utc))
    second = orchestrator.open_run(tenant_id='tenant-a', invoice_id='inv-9', started_at=datetime(2026, 4, 2, tzinfo=timezone.utc))
    assert first == second


def test_plan_change_rejects_cross_currency_without_fx() -> None:
    try:
        PlanChangePolicy().quote(
            current_plan=_plan(TenantPlan.STARTER, 29.0, 'USD'),
            next_plan=_plan(TenantPlan.GROWTH, 99.0, 'EUR'),
            changed_at=datetime(2026, 4, 15, tzinfo=timezone.utc),
            cycle=SubscriptionLifecycleService().activate(tenant_id='tenant-a', subscription_id='sub-1', plan_id='starter', activated_at=datetime(2026, 4, 1, tzinfo=timezone.utc)).cycle,
        )
    except ValueError:
        pass
    else:
        raise AssertionError('expected FX guard to fail')


def test_reconciliation_accepts_rate_map() -> None:
    ledger = InMemoryLedgerStore()
    posting = LedgerPosting(
        posting_id='p-1',
        tenant_id='tenant-a',
        reference_type='invoice',
        reference_id='inv-1',
        entries=(
            LedgerEntry(tenant_id='tenant-a', entry_id='1', account_code='billing.accounts.ar', side='debit', amount_minor=1200, currency='USD', reference_type='invoice', reference_id='inv-1'),
            LedgerEntry(tenant_id='tenant-a', entry_id='2', account_code='billing.accounts.revenue', side='credit', amount_minor=1200, currency='USD', reference_type='invoice', reference_id='inv-1'),
        ),
    )
    ledger.append(posting)
    rollup = UsageRollupBuilder().build_daily([
        UsageRecord(tenant_id='tenant-a', meter_key='connector_calls', quantity=12, recorded_at=datetime(2026, 4, 9, tzinfo=timezone.utc))
    ])
    invoice = CommercialInvoiceEnvelope(invoice_id='inv-1', tenant_id='tenant-a', currency='USD', subtotal_minor=1000, tax_minor=200, total_minor=1200)
    report = BillingReconciliationService(ledger_store=ledger).reconcile(tenant_id='tenant-a', invoices=[invoice], usage_rollups=rollup, usage_rate_minor_by_meter={'connector_calls': 110})
    assert any(item.drift_key == 'usage_proxy_vs_ledger' for item in report.drifts)


def test_tax_bridge_uses_runtime_monetization_owner() -> None:
    tax = BillingTaxPolicyBridge().resolve(service=MonetizationService(), subtotal_minor=1000, context=TaxContext(country_code='NL'))
    assert tax.tax_amount_minor == 210


def test_payment_collection_replay_uses_original_collected_amount() -> None:
    invoice = InvoiceLifecycleService().issue(CommercialInvoiceEnvelope(invoice_id='inv-2', tenant_id='tenant-a', currency='USD', subtotal_minor=1000, tax_minor=200, total_minor=1200))
    store = InMemoryCollectionResultStore()
    orchestrator = PaymentCollectionOrchestrator(provider=_Provider(), result_store=store)
    _, first_result = orchestrator.collect(invoice=invoice, idempotency_key='x-2')
    partially_paid = InvoiceLifecycleService().record_payment(invoice, amount_minor=200)
    replayed_invoice, replayed_result = orchestrator.collect(invoice=partially_paid, idempotency_key='x-2')
    assert replayed_result is first_result
    assert replayed_invoice.paid_minor == 1200


def test_invoice_lifecycle_rejects_draft_payment_and_due_before_issue() -> None:
    lifecycle = InvoiceLifecycleService()
    draft = CommercialInvoiceEnvelope(invoice_id='inv-3', tenant_id='tenant-a', currency='USD', subtotal_minor=1000, tax_minor=200, total_minor=1200)
    try:
        lifecycle.record_payment(draft, amount_minor=100)
    except ValueError:
        pass
    else:
        raise AssertionError('expected draft payment to fail')
    try:
        lifecycle.issue(draft, issued_at=datetime(2026, 4, 10, tzinfo=timezone.utc), due_at=datetime(2026, 4, 9, tzinfo=timezone.utc))
    except ValueError:
        pass
    else:
        raise AssertionError('expected due_at before issued_at to fail')


def test_subscription_renewal_starts_from_cycle_end_when_renewed_early() -> None:
    svc = SubscriptionLifecycleService()
    envelope = svc.activate(tenant_id='tenant-a', subscription_id='sub-2', plan_id='growth', activated_at=datetime(2026, 4, 1, tzinfo=timezone.utc))
    renewed = svc.renew_cycle(envelope, now=datetime(2026, 4, 15, tzinfo=timezone.utc))
    assert renewed.cycle.start_at == envelope.cycle.end_at


def test_dunning_store_is_scoped_by_tenant_and_invoice() -> None:
    schedule_store = InMemoryDunningScheduleStore()
    orchestrator = DunningOrchestrator(store=schedule_store)
    a = orchestrator.open_run(tenant_id='tenant-a', invoice_id='inv-1', started_at=datetime(2026, 4, 1, tzinfo=timezone.utc))
    b = orchestrator.open_run(tenant_id='tenant-b', invoice_id='inv-1', started_at=datetime(2026, 4, 2, tzinfo=timezone.utc))
    assert a != b
    assert orchestrator.due_actions(tenant_id='tenant-a', invoice_id='inv-1', now=datetime(2026, 4, 10, tzinfo=timezone.utc))
    assert orchestrator.due_actions(tenant_id='tenant-b', invoice_id='inv-1', now=datetime(2026, 4, 10, tzinfo=timezone.utc))


def test_reconciliation_flags_mixed_invoice_currency() -> None:
    ledger = InMemoryLedgerStore()
    posting = LedgerPosting(
        posting_id='p-mixed',
        tenant_id='tenant-a',
        reference_type='invoice',
        reference_id='inv-mixed',
        entries=(
            LedgerEntry(tenant_id='tenant-a', entry_id='1', account_code='billing.accounts.ar', side='debit', amount_minor=1200, currency='USD', reference_type='invoice', reference_id='inv-mixed'),
            LedgerEntry(tenant_id='tenant-a', entry_id='2', account_code='billing.accounts.revenue', side='credit', amount_minor=1200, currency='USD', reference_type='invoice', reference_id='inv-mixed'),
        ),
    )
    ledger.append(posting)
    invoices = [
        CommercialInvoiceEnvelope(invoice_id='inv-usd', tenant_id='tenant-a', currency='USD', subtotal_minor=1000, tax_minor=200, total_minor=1200),
        CommercialInvoiceEnvelope(invoice_id='inv-eur', tenant_id='tenant-a', currency='EUR', subtotal_minor=1000, tax_minor=200, total_minor=1200),
    ]
    report = BillingReconciliationService(ledger_store=ledger).reconcile(tenant_id='tenant-a', invoices=invoices, usage_rollups=())
    assert any(item.drift_key == 'mixed_invoice_currency' for item in report.drifts)


def test_payment_collection_store_is_tenant_scoped_for_same_invoice_id() -> None:
    store = InMemoryCollectionResultStore()
    orchestrator = PaymentCollectionOrchestrator(provider=_Provider(), result_store=store)
    invoice_a = InvoiceLifecycleService().issue(CommercialInvoiceEnvelope(invoice_id='shared-invoice', tenant_id='tenant-a', currency='USD', subtotal_minor=1000, tax_minor=200, total_minor=1200))
    invoice_b = InvoiceLifecycleService().issue(CommercialInvoiceEnvelope(invoice_id='shared-invoice', tenant_id='tenant-b', currency='USD', subtotal_minor=500, tax_minor=100, total_minor=600))
    orchestrator.collect(invoice=invoice_a, idempotency_key='a-1')
    orchestrator.collect(invoice=invoice_b, idempotency_key='b-1')
    assert len(store.list_for_invoice('shared-invoice', tenant_id='tenant-a')) == 1
    assert len(store.list_for_invoice('shared-invoice', tenant_id='tenant-b')) == 1
    assert len(store.list_for_invoice('shared-invoice')) == 2


def test_payment_collection_rejects_provider_result_mismatch() -> None:
    class _BadProvider(_Provider):
        def collect(self, attempt):
            result = super().collect(attempt)
            return replace(result, tenant_id='tenant-bad')

    invoice = InvoiceLifecycleService().issue(CommercialInvoiceEnvelope(invoice_id='inv-bad', tenant_id='tenant-a', currency='USD', subtotal_minor=1000, tax_minor=200, total_minor=1200))
    orchestrator = PaymentCollectionOrchestrator(provider=_BadProvider(), result_store=InMemoryCollectionResultStore())
    try:
        orchestrator.collect(invoice=invoice, idempotency_key='bad-1')
    except ValueError:
        pass
    else:
        raise AssertionError('expected provider result mismatch to fail')


def test_dunning_store_rejects_action_scope_mismatch() -> None:
    store = InMemoryDunningScheduleStore()
    bad_action = DunningAction(
        invoice_id='inv-y',
        tenant_id='tenant-a',
        attempt_no=1,
        execute_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
        channel='email',
        template_key='billing.dunning.attempt_1',
    )
    try:
        store.save(tenant_id='tenant-a', invoice_id='inv-x', actions=(bad_action,))
    except ValueError:
        pass
    else:
        raise AssertionError('expected dunning action scope mismatch to fail')


def test_spend_guard_fails_closed_on_mixed_currency_ledger() -> None:
    ledger = InMemoryLedgerStore()
    usd_posting = LedgerPosting(
        posting_id='p-usd',
        tenant_id='tenant-a',
        reference_type='invoice',
        reference_id='inv-usd',
        entries=(
            LedgerEntry(tenant_id='tenant-a', entry_id='1', account_code='billing.accounts.ar', side='debit', amount_minor=1000, currency='USD', reference_type='invoice', reference_id='inv-usd'),
            LedgerEntry(tenant_id='tenant-a', entry_id='2', account_code='billing.accounts.revenue', side='credit', amount_minor=1000, currency='USD', reference_type='invoice', reference_id='inv-usd'),
        ),
    )
    eur_posting = LedgerPosting(
        posting_id='p-eur',
        tenant_id='tenant-a',
        reference_type='invoice',
        reference_id='inv-eur',
        entries=(
            LedgerEntry(tenant_id='tenant-a', entry_id='3', account_code='billing.accounts.ar', side='debit', amount_minor=900, currency='EUR', reference_type='invoice', reference_id='inv-eur'),
            LedgerEntry(tenant_id='tenant-a', entry_id='4', account_code='billing.accounts.revenue', side='credit', amount_minor=900, currency='EUR', reference_type='invoice', reference_id='inv-eur'),
        ),
    )
    ledger.append(usd_posting)
    ledger.append(eur_posting)
    verdict = SpendGuard(ledger_store=ledger).check(policy=SpendLimitPolicy(tenant_id='tenant-a', currency='USD', cycle_limit_minor=5000), pending_minor=100)
    assert verdict.allowed is False
    assert verdict.reason == 'mixed_currency_ledger'


def test_plan_change_quote_validates_fraction_bounds() -> None:
    quote = PlanChangeQuote(from_plan_id='starter', to_plan_id='growth', proration_fraction=1.1, delta_minor=100, currency='USD', effective_immediately=True)
    try:
        quote.validate()
    except ValueError:
        pass
    else:
        raise AssertionError('expected invalid proration fraction to fail')


def test_payment_customer_profile_normalizes_currency() -> None:
    profile = PaymentCustomerProfile(tenant_id='tenant-a', provider_customer_id=' cust-1 ', default_currency=' usd ')
    normalized = profile.normalized_copy()
    assert normalized.default_currency == 'USD'
    assert normalized.provider_customer_id == 'cust-1'



def test_invoice_validate_enforces_state_specific_consistency() -> None:
    try:
        CommercialInvoiceEnvelope(
            invoice_id='inv-bad-paid',
            tenant_id='tenant-a',
            currency='USD',
            subtotal_minor=1000,
            tax_minor=200,
            total_minor=1200,
            status=__import__('billing.commercial_cycle_contract', fromlist=['InvoiceLifecycleStatus']).InvoiceLifecycleStatus.PAID,
            paid_minor=1000,
            issued_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        ).validate()
    except ValueError:
        pass
    else:
        raise AssertionError('expected paid invoice consistency validation to fail')


def test_subscription_validate_requires_canceled_at_for_canceled_status() -> None:
    cycle = SubscriptionLifecycleService().activate(
        tenant_id='tenant-a', subscription_id='sub-cancel', plan_id='growth', activated_at=datetime(2026, 4, 1, tzinfo=timezone.utc)
    ).cycle
    try:
        __import__('billing.commercial_cycle_contract', fromlist=['SubscriptionCommercialEnvelope', 'SubscriptionLifecycleStatus']).SubscriptionCommercialEnvelope(
            tenant_id='tenant-a',
            subscription_id='sub-cancel',
            plan_id='growth',
            status=__import__('billing.commercial_cycle_contract', fromlist=['SubscriptionLifecycleStatus']).SubscriptionLifecycleStatus.CANCELED,
            cycle=cycle,
        ).validate()
    except ValueError:
        pass
    else:
        raise AssertionError('expected canceled subscription without canceled_at to fail')


def test_payment_collection_rejects_idempotency_collision_with_different_result() -> None:
    store = InMemoryCollectionResultStore()
    first = __import__('billing.commercial_cycle_contract', fromlist=['CommercialCollectionResult']).CommercialCollectionResult(
        invoice_id='inv-1', tenant_id='tenant-a', provider_name='dummy', successful=True, external_reference='ok:1'
    )
    second = __import__('billing.commercial_cycle_contract', fromlist=['CommercialCollectionResult']).CommercialCollectionResult(
        invoice_id='inv-1', tenant_id='tenant-a', provider_name='dummy', successful=True, external_reference='ok:2'
    )
    store.append(first, idempotency_key='same')
    try:
        store.append(second, idempotency_key='same')
    except ValueError:
        pass
    else:
        raise AssertionError('expected idempotency collision to fail')


def test_payment_collection_rejects_draft_invoice_collection() -> None:
    draft = CommercialInvoiceEnvelope(invoice_id='draft-collect', tenant_id='tenant-a', currency='USD', subtotal_minor=1000, tax_minor=200, total_minor=1200)
    orchestrator = PaymentCollectionOrchestrator(provider=_Provider(), result_store=InMemoryCollectionResultStore())
    try:
        orchestrator.collect(invoice=draft, idempotency_key='draft-x')
    except ValueError:
        pass
    else:
        raise AssertionError('expected draft invoice collection to fail')


def test_dunning_open_run_requires_timezone_aware_started_at() -> None:
    orchestrator = DunningOrchestrator(store=InMemoryDunningScheduleStore())
    try:
        orchestrator.open_run(tenant_id='tenant-a', invoice_id='inv-naive', started_at=datetime(2026, 4, 1))
    except ValueError:
        pass
    else:
        raise AssertionError('expected naive started_at to fail')


def test_reconciliation_flags_mixed_ledger_currency() -> None:
    ledger = InMemoryLedgerStore()
    posting_usd = LedgerPosting(
        posting_id='p-usd', tenant_id='tenant-a', reference_type='invoice', reference_id='inv-1',
        entries=(
            LedgerEntry(tenant_id='tenant-a', entry_id='1', account_code='billing.accounts.ar', side='debit', amount_minor=1000, currency='USD', reference_type='invoice', reference_id='inv-1'),
            LedgerEntry(tenant_id='tenant-a', entry_id='2', account_code='billing.accounts.revenue', side='credit', amount_minor=1000, currency='USD', reference_type='invoice', reference_id='inv-1'),
        ),
    )
    posting_eur = LedgerPosting(
        posting_id='p-eur', tenant_id='tenant-a', reference_type='invoice', reference_id='inv-2',
        entries=(
            LedgerEntry(tenant_id='tenant-a', entry_id='3', account_code='billing.accounts.ar', side='debit', amount_minor=900, currency='EUR', reference_type='invoice', reference_id='inv-2'),
            LedgerEntry(tenant_id='tenant-a', entry_id='4', account_code='billing.accounts.revenue', side='credit', amount_minor=900, currency='EUR', reference_type='invoice', reference_id='inv-2'),
        ),
    )
    ledger.append(posting_usd)
    ledger.append(posting_eur)
    report = BillingReconciliationService(ledger_store=ledger).reconcile(tenant_id='tenant-a', invoices=(), usage_rollups=())
    assert any(item.drift_key == 'mixed_ledger_currency' for item in report.drifts)



def test_inmemory_ledger_store_rejects_posting_id_collision_with_different_payload() -> None:
    ledger = InMemoryLedgerStore()
    first = LedgerPosting(
        posting_id='p-collide', tenant_id='tenant-a', reference_type='invoice', reference_id='inv-1',
        entries=(
            LedgerEntry(tenant_id='tenant-a', entry_id='1', account_code='billing.accounts.ar', side='debit', amount_minor=500, currency='USD', reference_type='invoice', reference_id='inv-1'),
            LedgerEntry(tenant_id='tenant-a', entry_id='2', account_code='billing.accounts.revenue', side='credit', amount_minor=500, currency='USD', reference_type='invoice', reference_id='inv-1'),
        ),
    )
    second = LedgerPosting(
        posting_id='p-collide', tenant_id='tenant-a', reference_type='invoice', reference_id='inv-1',
        entries=(
            LedgerEntry(tenant_id='tenant-a', entry_id='3', account_code='billing.accounts.ar', side='debit', amount_minor=600, currency='USD', reference_type='invoice', reference_id='inv-1'),
            LedgerEntry(tenant_id='tenant-a', entry_id='4', account_code='billing.accounts.revenue', side='credit', amount_minor=600, currency='USD', reference_type='invoice', reference_id='inv-1'),
        ),
    )
    ledger.append(first)
    try:
        ledger.append(second)
    except ValueError:
        pass
    else:
        raise AssertionError('expected in-memory posting collision to fail')


def test_payment_collection_replay_rejects_draft_invoice_even_with_existing_result() -> None:
    issued = InvoiceLifecycleService().issue(CommercialInvoiceEnvelope(invoice_id='inv-draft-replay', tenant_id='tenant-a', currency='USD', subtotal_minor=1000, tax_minor=200, total_minor=1200))
    orchestrator = PaymentCollectionOrchestrator(provider=_Provider(), result_store=InMemoryCollectionResultStore())
    orchestrator.collect(invoice=issued, idempotency_key='idem-draft-replay')
    draft = CommercialInvoiceEnvelope(invoice_id='inv-draft-replay', tenant_id='tenant-a', currency='USD', subtotal_minor=1000, tax_minor=200, total_minor=1200)
    try:
        orchestrator.collect(invoice=draft, idempotency_key='idem-draft-replay')
    except ValueError:
        pass
    else:
        raise AssertionError('expected replay into draft invoice to fail')


def test_dunning_due_actions_do_not_repeat_after_mark_executed() -> None:
    orchestrator = DunningOrchestrator(store=InMemoryDunningScheduleStore())
    actions = orchestrator.open_run(tenant_id='tenant-a', invoice_id='inv-due-once', started_at=datetime(2026, 4, 1, tzinfo=timezone.utc))
    due = orchestrator.due_actions(tenant_id='tenant-a', invoice_id='inv-due-once', now=datetime(2026, 4, 10, tzinfo=timezone.utc))
    assert due and due[0].attempt_no == actions[0].attempt_no
    orchestrator.mark_action_executed(tenant_id='tenant-a', invoice_id='inv-due-once', attempt_no=actions[0].attempt_no)
    due_again = orchestrator.due_actions(tenant_id='tenant-a', invoice_id='inv-due-once', now=datetime(2026, 4, 10, tzinfo=timezone.utc))
    assert all(item.attempt_no != actions[0].attempt_no for item in due_again)


def test_dunning_store_rejects_duplicate_attempt_numbers() -> None:
    store = InMemoryDunningScheduleStore()
    action = DunningAction(
        tenant_id='tenant-a', invoice_id='inv-dup-attempt', attempt_no=1, execute_at=datetime(2026, 4, 2, tzinfo=timezone.utc), channel='email', template_key='billing.dunning.attempt_1'
    )
    try:
        store.save(tenant_id='tenant-a', invoice_id='inv-dup-attempt', actions=(action, replace(action, channel='operator')))
    except ValueError:
        pass
    else:
        raise AssertionError('expected duplicate dunning attempt numbers to fail')



def test_subscription_state_guards_and_cancel_cleanup() -> None:
    service = SubscriptionLifecycleService()
    active = service.activate(tenant_id='tenant-a', subscription_id='sub-1', plan_id='plan-pro')
    with pytest.raises(ValueError):
        service.enter_grace(active)
    past_due = service.mark_past_due(active, now=utc_now())
    grace = service.enter_grace(past_due, now=utc_now())
    canceled = service.cancel(grace, canceled_at=utc_now())
    assert canceled.status is SubscriptionLifecycleStatus.CANCELED
    assert canceled.grace_until is None
    assert canceled.trial_ends_at is None
    with pytest.raises(ValueError):
        service.renew_cycle(canceled, now=utc_now())


def test_invoice_issue_only_from_draft_and_uncollectible_constraints() -> None:
    lifecycle = InvoiceLifecycleService()
    draft = CommercialInvoiceEnvelope(tenant_id='tenant-a', invoice_id='inv-state', subscription_id=None, currency='USD', total_minor=1000)
    issued = lifecycle.issue(draft, issued_at=utc_now())
    with pytest.raises(ValueError):
        lifecycle.issue(issued, issued_at=utc_now())
    with pytest.raises(ValueError):
        lifecycle.mark_uncollectible(draft)


def test_dunning_mark_executed_requires_existing_attempt() -> None:
    store = InMemoryDunningScheduleStore()
    now = utc_now()
    action = DunningAction(invoice_id='inv-1', tenant_id='tenant-a', attempt_no=1, execute_at=now, channel='email', template_key='tpl')
    store.save(tenant_id='tenant-a', invoice_id='inv-1', actions=(action,))
    with pytest.raises(LookupError):
        store.mark_executed(tenant_id='tenant-a', invoice_id='inv-1', attempt_no=2)


def test_payment_collection_replay_detects_provider_mismatch() -> None:
    invoice = InvoiceLifecycleService().issue(
        CommercialInvoiceEnvelope(tenant_id='tenant-a', invoice_id='inv-provider', subscription_id=None, currency='USD', total_minor=500),
        issued_at=utc_now(),
    )
    store = InMemoryCollectionResultStore()
    first = PaymentCollectionOrchestrator(provider=_Provider(), result_store=store)
    _, result = first.collect(invoice=invoice, idempotency_key='idem-provider')
    assert result.successful is True
    
    @dataclass(frozen=True)
    class _OtherProvider(PaymentProviderContract):
        def provider_name(self) -> str:
            return 'other-provider'

        def ensure_customer(self, *, tenant_id: str, email: str | None = None, metadata=None):
            raise NotImplementedError

        def collect(self, attempt):
            raise NotImplementedError

        def refund(self, *, invoice_id: str, tenant_id: str, amount_minor: int, currency: str, reason: str, metadata=None):
            return {'status': 'processed'}

    second = PaymentCollectionOrchestrator(provider=_OtherProvider(), result_store=store)
    with pytest.raises(ValueError):
        second.collect(invoice=invoice, idempotency_key='idem-provider')

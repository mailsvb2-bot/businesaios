from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from billing.chargeback_orchestrator import ChargebackCase, ChargebackOrchestrator, InMemoryChargebackStore
from billing.commercial_cycle_contract import InvoiceLifecycleStatus
from billing.invoice_lifecycle import CommercialInvoiceEnvelope
from billing.ledger_store import InMemoryLedgerStore
from billing.refund_orchestrator import InMemoryRefundStore, RefundOrchestrator, RefundRequest, RefundResult
from runtime.monetization import MonetizationService

NOW = datetime(2026, 7, 18, tzinfo=UTC)


def _invoice(*, status=InvoiceLifecycleStatus.PAID, paid=100, total=100, metadata=None):
    issued = None if status is InvoiceLifecycleStatus.DRAFT else NOW
    return CommercialInvoiceEnvelope(
        tenant_id="tenant-a", invoice_id="invoice-a", subscription_id="sub-a", currency="USD",
        subtotal_minor=total, tax_minor=0, total_minor=total, status=status, issued_at=issued,
        due_at=None if issued is None else issued + timedelta(days=30), paid_minor=paid,
        metadata={} if metadata is None else metadata,
    )


class _Provider:
    def __init__(self, *, name="provider-a", payload=None):
        self.name = name
        self.payload = {"refund_id":"refund-provider","external_reference":"external-a"} if payload is None else payload
        self.calls=[]
    def provider_name(self): return self.name
    def refund(self, **kwargs): self.calls.append(kwargs); return self.payload


class _Metrics:
    def __init__(self): self.calls=[]
    def inc(self, **kwargs): self.calls.append(kwargs)


def test_refund_request_and_result_validation_matrix() -> None:
    valid=RefundRequest("tenant-a","invoice-a","user-a",1,"USD","reason","provider",NOW,"key"); valid.validate()
    for name,value in {"invoice_id":"","user_id":"","amount_minor":0,"currency":"","reason":"","provider_name":"","requested_at":datetime(2026,1,1),"idempotency_key":" "}.items():
        with pytest.raises(ValueError): replace(valid,**{name:value}).validate()
    with pytest.raises(ValueError): replace(valid,tenant_id=" ").validate()
    result=RefundResult("tenant-a","invoice-a","refund-a",1,"USD","provider","external",NOW,{}); result.validate()
    for name,value in {"invoice_id":"","refund_id":"","amount_minor":0,"currency":"","provider_name":"","external_reference":"","processed_at":datetime(2026,1,1)}.items():
        with pytest.raises(ValueError): replace(result,**{name:value}).validate()
    with pytest.raises(ValueError): replace(result,tenant_id="").validate()


def test_in_memory_refund_store_replay_collision_and_blank_key() -> None:
    store=InMemoryRefundStore(); result=RefundResult("tenant-a","invoice-a","refund-a",10,"USD","provider","external",NOW,{})
    assert store.save(result,idempotency_key=" key ")==result
    assert store.save(result,idempotency_key="key")==result
    assert store.save(result)==result
    assert store.list_for_invoice(tenant_id="tenant-a",invoice_id="invoice-a")== (result,)
    assert store.get_by_idempotency(tenant_id="tenant-a",invoice_id="invoice-a",idempotency_key=" key ")==result
    assert store.get_by_idempotency(tenant_id="tenant-b",invoice_id="invoice-a",idempotency_key="key") is None
    blank1=replace(result,refund_id="blank-1",processed_at=NOW+timedelta(seconds=1)); blank2=replace(result,refund_id="blank-2",processed_at=NOW+timedelta(seconds=2))
    store.save(blank1,idempotency_key=" "); store.save(blank2,idempotency_key=" ")
    with pytest.raises(ValueError,match="idempotency_key collision"): store.save(replace(result,refund_id="other",amount_minor=11),idempotency_key="key")
    with pytest.raises(ValueError,match="refund_id collision"): store.save(replace(result,amount_minor=11))


def test_refund_orchestrator_new_partial_full_and_provider_affinity() -> None:
    provider=_Provider(); ledger=InMemoryLedgerStore(); money=MonetizationService(); metrics=_Metrics()
    orch=RefundOrchestrator(provider=provider,ledger_store=ledger,monetization_service=money,metrics=metrics,clearing_account=" ",contra_revenue_account=" ")
    updated,result,record,posting=orch.refund(invoice=_invoice(),user_id="user-a",amount_minor=30,reason="reason",idempotency_key="key",metadata={"preferred_provider":"provider-a"})
    assert updated.status is InvoiceLifecycleStatus.PARTIALLY_PAID and updated.paid_minor==70
    assert result.refund_id=="refund-provider" and record.amount_minor==30
    assert posting.entries[0].account_code=="billing.accounts.refunds" and posting.entries[1].account_code=="billing.accounts.cash"
    assert provider.calls[0]["metadata"]["idempotency_key"]=="key"
    assert metrics.calls[0]["metric_name"]=="billing_refunds_total"
    provider2=_Provider(payload={"external_reference":"external-only"})
    updated2,result2,_,_=RefundOrchestrator(provider=provider2,ledger_store=InMemoryLedgerStore(),monetization_service=MonetizationService()).refund(invoice=_invoice(),user_id="u",amount_minor=100,reason="r",idempotency_key="key-2")
    assert updated2.status is InvoiceLifecycleStatus.ISSUED and updated2.paid_minor==0 and result2.refund_id
    with pytest.raises(ValueError,match="provider must match"):
        RefundOrchestrator(provider=_Provider(name="other"),ledger_store=InMemoryLedgerStore(),monetization_service=MonetizationService()).refund(invoice=_invoice(metadata={"provider_customer_id":"provider-a:customer"}),user_id="u",amount_minor=1,reason="r",idempotency_key="k")


def test_refund_orchestrator_replay_statuses_and_idempotent_invoice() -> None:
    store=InMemoryRefundStore(); ledger=InMemoryLedgerStore(); provider=_Provider(); money=MonetizationService(); orch=RefundOrchestrator(provider=provider,ledger_store=ledger,monetization_service=money,refund_store=store)
    first_invoice,first,_,posting=orch.refund(invoice=_invoice(),user_id="u",amount_minor=40,reason="r",idempotency_key="key")
    replay_invoice,replay,replay_record,replay_posting=orch.refund(invoice=_invoice(),user_id="u",amount_minor=999,reason="different",idempotency_key="key")
    assert replay==first and replay_invoice.paid_minor==60 and replay_invoice.status is InvoiceLifecycleStatus.PARTIALLY_PAID
    assert replay_record.refund_id==first.refund_id and replay_posting==posting
    unchanged,*_=orch.refund(invoice=first_invoice,user_id="u",amount_minor=999,reason="different",idempotency_key="key"); assert unchanged==first_invoice
    store2=InMemoryRefundStore(); existing=replace(first,refund_id="zero",amount_minor=100); store2.save(existing,idempotency_key="zero-key")
    zero_invoice,*_=RefundOrchestrator(provider=provider,ledger_store=InMemoryLedgerStore(),monetization_service=money,refund_store=store2).refund(invoice=_invoice(),user_id="u",amount_minor=999,reason="r",idempotency_key="zero-key")
    assert zero_invoice.status is InvoiceLifecycleStatus.ISSUED and zero_invoice.paid_minor==0


def test_refund_orchestrator_fail_closed_matrix() -> None:
    orch=RefundOrchestrator(provider=_Provider(),ledger_store=InMemoryLedgerStore(),monetization_service=MonetizationService())
    with pytest.raises(ValueError,match="eligible"): orch.refund(invoice=_invoice(status=InvoiceLifecycleStatus.DRAFT,paid=0),user_id="u",amount_minor=1,reason="r",idempotency_key="k")
    with pytest.raises(ValueError,match="idempotency"): orch.refund(invoice=_invoice(),user_id="u",amount_minor=1,reason="r",idempotency_key=" ")
    with pytest.raises(ValueError,match="exceed"): orch.refund(invoice=_invoice(status=InvoiceLifecycleStatus.PARTIALLY_PAID,paid=20),user_id="u",amount_minor=21,reason="r",idempotency_key="k")
    with pytest.raises(ValueError,match="missing external"):
        RefundOrchestrator(provider=_Provider(payload={}),ledger_store=InMemoryLedgerStore(),monetization_service=MonetizationService()).refund(invoice=_invoice(),user_id="u",amount_minor=1,reason="r",idempotency_key="k")
    assert RefundOrchestrator._extract_provider_affinity(invoice=_invoice(),metadata={"routed_provider":" routed "})=="routed"
    assert RefundOrchestrator._extract_provider_affinity(invoice=_invoice(metadata={"provider_customer_id":"plain"})) is None


def test_chargeback_case_and_store_validation_replay_and_collision() -> None:
    case=ChargebackCase("tenant-a","invoice-a","user-a",10,"USD","reason",NOW,"case-a","key",{}); case.validate()
    for name,value in {"invoice_id":"","user_id":"","amount_minor":0,"currency":"","reason":"","opened_at":datetime(2026,1,1),"idempotency_key":" "}.items():
        with pytest.raises(ValueError): replace(case,**{name:value}).validate()
    with pytest.raises(ValueError): replace(case,tenant_id="").validate()
    store=InMemoryChargebackStore(); assert store.save(case,idempotency_key=" key ")==case; assert store.save(case,idempotency_key="key")==case; assert store.save(case)==case
    assert store.list_for_invoice(tenant_id="tenant-a",invoice_id="invoice-a")== (case,)
    assert store.get_by_idempotency(tenant_id="tenant-a",invoice_id="invoice-a",idempotency_key="key")==case
    with pytest.raises(ValueError,match="idempotency"): store.save(replace(case,case_id="other",amount_minor=11),idempotency_key="key")
    with pytest.raises(ValueError,match="case collision"): store.save(replace(case,amount_minor=11))
    other=replace(case,case_id="case-b",opened_at=NOW+timedelta(seconds=1),idempotency_key=None); store.save(other); assert store.save(other)==other


def test_chargeback_orchestrator_new_replay_and_status_matrix() -> None:
    store=InMemoryChargebackStore(); ledger=InMemoryLedgerStore(); money=MonetizationService(); metrics=_Metrics(); orch=ChargebackOrchestrator(ledger_store=ledger,monetization_service=money,case_store=store,metrics=metrics,receivable_account=" ",chargeback_account=" ")
    updated,case,record,posting=orch.open_case(invoice=_invoice(),user_id="u",amount_minor=30,reason="r",idempotency_key="key")
    assert updated.status is InvoiceLifecycleStatus.PARTIALLY_PAID and updated.paid_minor==70 and record.amount_minor==30 and posting.entries[0].account_code=="billing.accounts.chargebacks"
    replay_invoice,replay_case,replay_record,replay_posting=orch.open_case(invoice=_invoice(),user_id="x",amount_minor=999,reason="x",idempotency_key="key")
    assert replay_case==case and replay_invoice.paid_minor==70 and replay_record.chargeback_id==case.case_id and replay_posting==posting
    unchanged,*_=orch.open_case(invoice=updated,user_id="x",amount_minor=999,reason="x",idempotency_key="key"); assert unchanged==updated
    full,*_=ChargebackOrchestrator(ledger_store=InMemoryLedgerStore(),monetization_service=MonetizationService()).open_case(invoice=_invoice(),user_id="u",amount_minor=100,reason="r"); assert full.status is InvoiceLifecycleStatus.UNCOLLECTIBLE
    issued,*_=ChargebackOrchestrator(ledger_store=InMemoryLedgerStore(),monetization_service=MonetizationService()).open_case(invoice=_invoice(status=InvoiceLifecycleStatus.PARTIALLY_PAID,paid=20),user_id="u",amount_minor=20,reason="r"); assert issued.status is InvoiceLifecycleStatus.ISSUED


def test_chargeback_orchestrator_fail_closed() -> None:
    orch=ChargebackOrchestrator(ledger_store=InMemoryLedgerStore(),monetization_service=MonetizationService())
    with pytest.raises(ValueError,match="eligible"): orch.open_case(invoice=_invoice(status=InvoiceLifecycleStatus.DRAFT,paid=0),user_id="u",amount_minor=1,reason="r")
    with pytest.raises(ValueError,match="exceed"): orch.open_case(invoice=_invoice(status=InvoiceLifecycleStatus.PARTIALLY_PAID,paid=10),user_id="u",amount_minor=11,reason="r")

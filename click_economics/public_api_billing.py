from __future__ import annotations

from typing import Any, Mapping

from billing.commercial_cycle_contract import (
    CommercialCollectionAttempt,
    CommercialCollectionResult,
    InvoiceLifecycleStatus,
    utc_now,
)
from billing.invoice_lifecycle import CommercialInvoiceEnvelope, InvoiceLifecycleService
from billing.payment_collection import PaymentCollectionOrchestrator
from billing.payment_provider_contract import PaymentCustomerProfile, PaymentProviderContract

from .contracts import (
    ClickBillingCollectionPreview,
    ClickBillingExecutionRecord,
    ClickBillingHandoffRecord,
    ClickBillingInvoicePreview,
    ClickBillingProviderDispatchRecord,
    ClickBillingSettlementRecord,
)
from .public_api_core import (
    _resolve_currency,
    _safe_dict,
    build_click_billable_fact_contract_from_client_outcome,
    build_click_billable_fact_from_client_outcome,
    build_click_commercial_fact_from_client_outcome,
)


class _PreviewPaymentProvider(PaymentProviderContract):
    def provider_name(self) -> str:
        return 'click_preview_provider'

    def ensure_customer(self, *, tenant_id: str, email: str | None = None, metadata: Mapping[str, object] | None = None) -> PaymentCustomerProfile:
        return PaymentCustomerProfile(tenant_id=str(tenant_id), provider_customer_id=f'click-preview:{tenant_id}', default_currency=str((metadata or {}).get('currency') or 'USD'))

    def collect(self, attempt: CommercialCollectionAttempt) -> CommercialCollectionResult:
        return CommercialCollectionResult(
            invoice_id=attempt.invoice_id,
            tenant_id=attempt.tenant_id,
            provider_name=self.provider_name(),
            successful=True,
            external_reference=f'preview:{attempt.idempotency_key}',
            retryable=False,
            metadata={'owner': 'click_economics.preview_payment_provider', 'currency': attempt.currency, 'collected_amount_minor': attempt.amount_minor, 'scheduled_at': attempt.scheduled_at.isoformat()},
        )

    def refund(self, *, invoice_id: str, tenant_id: str, amount_minor: int, currency: str, reason: str, metadata: Mapping[str, object] | None = None) -> Mapping[str, object]:
        return {'invoice_id': invoice_id, 'tenant_id': tenant_id, 'provider_name': self.provider_name(), 'amount_minor': int(amount_minor), 'currency': str(currency), 'reason': str(reason), 'metadata': dict(metadata or {})}


def build_click_billing_handoff_payload_from_client_outcome(*, truth_snapshot: Mapping[str, Any], lifecycle: object | None) -> dict[str, Any]:
    commercial = build_click_commercial_fact_from_client_outcome(truth_snapshot=truth_snapshot, lifecycle=lifecycle)
    contract = build_click_billable_fact_contract_from_client_outcome(truth_snapshot=truth_snapshot, lifecycle=lifecycle)
    issues = list(commercial.issues)
    if contract is None:
        issues.append('click_billing_handoff_not_ready')
    evidence_refs = commercial.evidence_refs if contract is None else contract.evidence_refs
    return {
        'tenant_id': commercial.tenant_id,
        'business_id': commercial.business_id,
        'entity_id': commercial.entity_id,
        'handoff_ready': contract is not None,
        'billable_candidate': commercial.billable_candidate,
        'handoff_contract': None if contract is None else {
            'domain': contract.domain,
            'entity_id': contract.entity_id,
            'amount_minor': contract.amount_minor,
            'currency': contract.currency,
            'reason_code': contract.reason_code,
            'idempotency_key': contract.idempotency_key,
            'evidence_refs': contract.evidence_refs,
        },
        'issues': tuple(dict.fromkeys(str(item) for item in issues if str(item).strip())),
        'evidence_refs': tuple(str(item) for item in evidence_refs if str(item).strip()),
        'ready_for_export': bool(contract is not None and commercial.ready_for_export),
    }



def build_click_billing_handoff_record_from_client_outcome(*, truth_snapshot: Mapping[str, Any], lifecycle: object | None) -> ClickBillingHandoffRecord:
    payload = build_click_billing_handoff_payload_from_client_outcome(truth_snapshot=truth_snapshot, lifecycle=lifecycle)
    blockers = tuple(str(item) for item in tuple(payload.get('issues') or ()) if str(item).strip())
    handoff_ready = bool(payload.get('handoff_ready'))
    stages: list[str] = ['click_commercial_fact_observed']
    if bool(payload.get('billable_candidate')):
        stages.append('click_billable_candidate')
    if handoff_ready:
        stages.append('billing_handoff_ready')
        status = 'ready'
    elif bool(payload.get('billable_candidate')):
        stages.append('billing_handoff_blocked')
        status = 'blocked'
    else:
        status = 'pending'
    return ClickBillingHandoffRecord(
        tenant_id=str(payload.get('tenant_id') or ''),
        business_id=str(payload.get('business_id') or ''),
        entity_id=str(payload.get('entity_id') or ''),
        status=status,
        blockers=blockers,
        lifecycle_stages=tuple(stages),
        evidence_refs=tuple(str(item) for item in tuple(payload.get('evidence_refs') or ()) if str(item).strip()),
        ready_for_export=bool(payload.get('ready_for_export')),
        handoff_contract=payload.get('handoff_contract'),
    )



def build_click_billing_invoice_preview_from_client_outcome(*, truth_snapshot: Mapping[str, Any], lifecycle: object | None) -> ClickBillingInvoicePreview:
    record = build_click_billing_handoff_record_from_client_outcome(truth_snapshot=truth_snapshot, lifecycle=lifecycle)
    blockers = list(record.blockers)
    stages = list(record.lifecycle_stages)
    invoice_id = f"click-invoice:{record.entity_id}" if str(record.entity_id).strip() else ''
    invoice_preview: dict[str, object] | None = None
    total_minor = 0
    currency = 'USD'
    status = 'blocked'
    if record.handoff_contract is not None:
        contract = dict(record.handoff_contract)
        total_minor = int(contract.get('amount_minor') or 0)
        currency = str(contract.get('currency') or 'USD')
        lifecycle = InvoiceLifecycleService()
        draft = CommercialInvoiceEnvelope(
            tenant_id=record.tenant_id,
            invoice_id=invoice_id,
            currency=currency,
            subtotal_minor=total_minor,
            tax_minor=0,
            total_minor=total_minor,
            status=InvoiceLifecycleStatus.DRAFT,
            metadata={
                'economic_domain': 'click_economics',
                'entity_id': record.entity_id,
                'source_channel': contract.get('source_channel') or '',
                'reason_code': contract.get('reason_code') or 'qualified_click',
                'idempotency_key': contract.get('idempotency_key') or '',
            },
        )
        issued = lifecycle.issue(draft)
        invoice_preview = {
            'invoice_id': issued.invoice_id,
            'status': issued.status.value if hasattr(issued.status, 'value') else str(issued.status),
            'currency': issued.currency,
            'subtotal_minor': issued.subtotal_minor,
            'tax_minor': issued.tax_minor,
            'total_minor': issued.total_minor,
            'paid_minor': issued.paid_minor,
            'remaining_minor': issued.remaining_minor,
            'metadata': dict(issued.metadata),
        }
        stages.append('billing_invoice_preview_built')
        status = 'ready'
    else:
        blockers.append('billing_invoice_preview_not_ready')
        stages.append('billing_invoice_preview_blocked')
    return ClickBillingInvoicePreview(
        tenant_id=record.tenant_id,
        business_id=record.business_id,
        entity_id=record.entity_id,
        invoice_id=invoice_id,
        currency=currency,
        total_minor=total_minor,
        status=status,
        blockers=tuple(dict.fromkeys(str(item) for item in blockers if str(item).strip())),
        lifecycle_stages=tuple(dict.fromkeys(str(item) for item in stages if str(item).strip())),
        evidence_refs=record.evidence_refs,
        ready_for_export=bool(record.ready_for_export and invoice_preview is not None),
        invoice_preview=invoice_preview,
    )


def build_click_billing_collection_preview_from_client_outcome(*, truth_snapshot: Mapping[str, Any], lifecycle: object | None) -> ClickBillingCollectionPreview:
    invoice_preview = build_click_billing_invoice_preview_from_client_outcome(truth_snapshot=truth_snapshot, lifecycle=lifecycle)
    blockers = list(invoice_preview.blockers)
    stages = list(invoice_preview.lifecycle_stages)
    provider_name = ''
    collection_preview: dict[str, object] | None = None
    collectible_amount_minor = 0
    status = 'blocked'
    if invoice_preview.invoice_preview is not None and invoice_preview.total_minor > 0:
        provider = _PreviewPaymentProvider()
        orchestrator = PaymentCollectionOrchestrator(provider=provider)
        metadata = dict(invoice_preview.invoice_preview.get('metadata') or {})
        envelope = CommercialInvoiceEnvelope(
            tenant_id=invoice_preview.tenant_id,
            invoice_id=invoice_preview.invoice_id,
            currency=invoice_preview.currency,
            subtotal_minor=invoice_preview.total_minor,
            tax_minor=0,
            total_minor=invoice_preview.total_minor,
            status=InvoiceLifecycleStatus.ISSUED,
            issued_at=utc_now(),
            metadata=metadata,
        )
        collected_invoice, result = orchestrator.collect(invoice=envelope, idempotency_key=str(metadata.get('idempotency_key') or f'click-collect:{invoice_preview.entity_id}'))
        provider_name = result.provider_name
        collectible_amount_minor = int(result.metadata.get('collected_amount_minor', invoice_preview.total_minor) or invoice_preview.total_minor)
        collection_preview = {
            'invoice_id': collected_invoice.invoice_id,
            'invoice_status': collected_invoice.status.value if hasattr(collected_invoice.status, 'value') else str(collected_invoice.status),
            'provider_name': result.provider_name,
            'successful': bool(result.successful),
            'external_reference': result.external_reference,
            'collected_amount_minor': collectible_amount_minor,
            'remaining_minor': collected_invoice.remaining_minor,
            'metadata': dict(result.metadata),
        }
        stages.append('billing_collection_preview_built')
        status = 'ready'
    else:
        blockers.append('billing_collection_preview_not_ready')
        stages.append('billing_collection_preview_blocked')
    return ClickBillingCollectionPreview(
        tenant_id=invoice_preview.tenant_id,
        business_id=invoice_preview.business_id,
        entity_id=invoice_preview.entity_id,
        invoice_id=invoice_preview.invoice_id,
        provider_name=provider_name,
        currency=invoice_preview.currency,
        total_minor=invoice_preview.total_minor,
        collectible_amount_minor=collectible_amount_minor,
        status=status,
        blockers=tuple(dict.fromkeys(str(item) for item in blockers if str(item).strip())),
        lifecycle_stages=tuple(dict.fromkeys(str(item) for item in stages if str(item).strip())),
        evidence_refs=invoice_preview.evidence_refs,
        ready_for_export=bool(invoice_preview.ready_for_export and collection_preview is not None),
        collection_preview=collection_preview,
    )



def build_click_billing_execution_record_from_client_outcome(*, truth_snapshot: Mapping[str, Any], lifecycle: object | None) -> ClickBillingExecutionRecord:
    collection = build_click_billing_collection_preview_from_client_outcome(truth_snapshot=truth_snapshot, lifecycle=lifecycle)
    blockers = list(collection.blockers)
    stages = list(collection.lifecycle_stages)
    execution_result: dict[str, object] | None = None
    status = 'blocked'
    collected_amount_minor = 0
    provider_name = collection.provider_name
    if collection.collection_preview is not None and bool(collection.collection_preview.get('successful')):
        execution_result = {
            'invoice_id': str(collection.collection_preview.get('invoice_id') or collection.invoice_id),
            'provider_name': str(collection.collection_preview.get('provider_name') or collection.provider_name),
            'external_reference': str(collection.collection_preview.get('external_reference') or ''),
            'collected_amount_minor': int(collection.collection_preview.get('collected_amount_minor') or collection.collectible_amount_minor or 0),
            'remaining_minor': int(collection.collection_preview.get('remaining_minor') or 0),
            'successful': True,
            'execution_owner': 'billing.preview_owner_path',
        }
        provider_name = str(execution_result.get('provider_name') or provider_name)
        collected_amount_minor = int(execution_result.get('collected_amount_minor') or 0)
        stages.append('billing_collection_execution_materialized')
        status = 'executed'
    elif collection.collection_preview is not None:
        blockers.append('billing_collection_execution_not_successful')
        stages.append('billing_collection_execution_failed')
        status = 'failed'
    else:
        blockers.append('billing_collection_execution_not_ready')
        stages.append('billing_collection_execution_blocked')
    return ClickBillingExecutionRecord(
        tenant_id=collection.tenant_id,
        business_id=collection.business_id,
        entity_id=collection.entity_id,
        invoice_id=collection.invoice_id,
        provider_name=provider_name,
        currency=collection.currency,
        total_minor=collection.total_minor,
        collected_amount_minor=collected_amount_minor,
        status=status,
        blockers=tuple(dict.fromkeys(str(item) for item in blockers if str(item).strip())),
        lifecycle_stages=tuple(dict.fromkeys(str(item) for item in stages if str(item).strip())),
        evidence_refs=collection.evidence_refs,
        ready_for_export=bool(collection.ready_for_export and execution_result is not None),
        execution_result=execution_result,
    )



def build_click_billing_settlement_record_from_client_outcome(*, truth_snapshot: Mapping[str, Any], lifecycle: object | None) -> ClickBillingSettlementRecord:
    execution = build_click_billing_execution_record_from_client_outcome(truth_snapshot=truth_snapshot, lifecycle=lifecycle)
    blockers = list(execution.blockers)
    stages = list(execution.lifecycle_stages)
    settlement_result: dict[str, object] | None = None
    status = 'blocked'
    settled_amount_minor = 0
    if execution.execution_result is not None and bool(execution.execution_result.get('successful')):
        settled_amount_minor = int(execution.execution_result.get('collected_amount_minor') or execution.collected_amount_minor or 0)
        settlement_result = {
            'invoice_id': str(execution.execution_result.get('invoice_id') or execution.invoice_id),
            'provider_name': str(execution.execution_result.get('provider_name') or execution.provider_name),
            'external_reference': str(execution.execution_result.get('external_reference') or ''),
            'settled_amount_minor': settled_amount_minor,
            'settlement_owner': 'billing.owner_path.settlement_projection',
            'fully_settled': settled_amount_minor >= int(execution.total_minor or 0),
        }
        stages.append('billing_collection_settlement_materialized')
        status = 'settled' if settlement_result['fully_settled'] else 'partially_settled'
    else:
        blockers.append('billing_collection_settlement_not_ready')
        stages.append('billing_collection_settlement_blocked')
    return ClickBillingSettlementRecord(
        tenant_id=execution.tenant_id,
        business_id=execution.business_id,
        entity_id=execution.entity_id,
        invoice_id=execution.invoice_id,
        provider_name=execution.provider_name,
        currency=execution.currency,
        collected_amount_minor=execution.collected_amount_minor,
        settled_amount_minor=settled_amount_minor,
        status=status,
        blockers=tuple(dict.fromkeys(str(item) for item in blockers if str(item).strip())),
        lifecycle_stages=tuple(dict.fromkeys(str(item) for item in stages if str(item).strip())),
        evidence_refs=execution.evidence_refs,
        ready_for_export=bool(execution.ready_for_export and settlement_result is not None),
        settlement_result=settlement_result,
    )



def build_click_billing_provider_dispatch_from_client_outcome(*, truth_snapshot: Mapping[str, Any], lifecycle: object | None) -> ClickBillingProviderDispatchRecord:
    settlement = build_click_billing_settlement_record_from_client_outcome(truth_snapshot=truth_snapshot, lifecycle=lifecycle)
    blockers = list(settlement.blockers)
    stages = list(settlement.lifecycle_stages)
    provider_dispatch: dict[str, object] | None = None
    status = 'blocked'
    if settlement.settlement_result is not None and str(settlement.provider_name or '').strip():
        provider_dispatch = {
            'invoice_id': settlement.invoice_id,
            'provider_name': settlement.provider_name,
            'currency': settlement.currency,
            'settled_amount_minor': settlement.settled_amount_minor,
            'operation': 'capture_settlement_projection',
            'transport_owner': 'runtime._internal.http_transport',
            'dispatch_owner': 'billing.owner_path.provider_dispatch_projection',
            'idempotency_key': f"click-provider-dispatch:{settlement.entity_id}:{settlement.invoice_id}",
        }
        stages.append('billing_provider_dispatch_materialized')
        status = 'ready'
    else:
        blockers.append('billing_provider_dispatch_not_ready')
        stages.append('billing_provider_dispatch_blocked')
    return ClickBillingProviderDispatchRecord(
        tenant_id=settlement.tenant_id,
        business_id=settlement.business_id,
        entity_id=settlement.entity_id,
        invoice_id=settlement.invoice_id,
        provider_name=settlement.provider_name,
        currency=settlement.currency,
        settled_amount_minor=settlement.settled_amount_minor,
        status=status,
        blockers=tuple(dict.fromkeys(str(item) for item in blockers if str(item).strip())),
        lifecycle_stages=tuple(dict.fromkeys(str(item) for item in stages if str(item).strip())),
        evidence_refs=settlement.evidence_refs,
        ready_for_export=bool(settlement.ready_for_export and provider_dispatch is not None),
        provider_dispatch=provider_dispatch,
    )

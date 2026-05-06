from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from uuid import uuid4

from billing.client_outcome_dispute_classification_bridge import ClientOutcomeDisputeClassificationBridge
from billing.client_outcome_dispute_contract import ClientOutcomeDisputeCase
from billing.client_outcome_dispute_store import ClientOutcomeDisputeStore, ClientOutcomeReversalStore
from billing.client_outcome_negative_usage_builder import ClientOutcomeNegativeUsageBuilder
from billing.client_outcome_refund_window_policy import ClientOutcomeRefundWindowPolicy
from billing.dispute_policy import DisputePolicy
from lead_outcomes.client_outcome_contract import BillableClientRecord


CANON_CLIENT_OUTCOME_DISPUTE_SERVICE = True


@dataclass(frozen=True, slots=True)
class ClientOutcomeDisputeResolutionResult:
    dispute: ClientOutcomeDisputeCase
    negative_record: BillableClientRecord | None
    reversal_payload: dict[str, object] | None


class ClientOutcomeDisputeService:
    def __init__(
        self,
        *,
        dispute_store: ClientOutcomeDisputeStore,
        reversal_store: ClientOutcomeReversalStore,
        refund_window_policy: ClientOutcomeRefundWindowPolicy,
        negative_usage_builder: ClientOutcomeNegativeUsageBuilder,
        classification_bridge: ClientOutcomeDisputeClassificationBridge | None = None,
    ) -> None:
        self._dispute_store = dispute_store
        self._reversal_store = reversal_store
        self._refund_window_policy = refund_window_policy
        self._negative_usage_builder = negative_usage_builder
        self._classification_bridge = classification_bridge or ClientOutcomeDisputeClassificationBridge(
            dispute_policy=DisputePolicy(),
        )

    def _from_row(self, row: dict[str, object]) -> ClientOutcomeDisputeCase:
        return ClientOutcomeDisputeCase(
            dispute_id=str(row['dispute_id']),
            tenant_id=str(row['tenant_id']),
            business_id=str(row['business_id']),
            order_id=str(row['order_id']),
            lead_id=str(row['lead_id']),
            billable_record_id=str(row['billable_record_id']),
            opened_at=datetime.fromisoformat(str(row['opened_at'])),
            opened_by=str(row['opened_by']),
            reason_code=str(row['reason_code']),
            status=str(row['status']),
            resolution_code=str(row.get('resolution_code') or ''),
            notes=str(row.get('notes') or ''),
            metadata=dict(row.get('metadata') or {}),
        )

    def open_dispute(
        self,
        *,
        now: datetime,
        tenant_id: str,
        business_id: str,
        order_id: str,
        lead_id: str,
        billable_record_id: str,
        opened_by: str,
        reason_code: str,
        notes: str = '',
        record: BillableClientRecord | None = None,
        metadata: dict[str, object] | None = None,
    ) -> ClientOutcomeDisputeCase:
        classification_metadata = dict(metadata or {})
        if record is not None:
            classification = self._classification_bridge.classify(
                reason_code=reason_code,
                record=record,
                metadata=classification_metadata,
            )
            classification_payload = self._classification_bridge.build_payload(
                reason_code=reason_code,
                record=record,
                metadata=classification_metadata,
            )
            classification_metadata.setdefault('classification_case_type', classification.case_type)
            classification_metadata.setdefault('classification_severity', classification.severity)
            classification_metadata.setdefault('evidence_fingerprint', classification_payload['evidence_fingerprint'])
        else:
            classification_metadata.setdefault('evidence_fingerprint', f'manual:{billable_record_id}')

        duplicate = self._dispute_store.find_duplicate_open_case(
            tenant_id=tenant_id,
            order_id=order_id,
            lead_id=lead_id,
            billable_record_id=billable_record_id,
            reason_code=reason_code,
            evidence_fingerprint=str(classification_metadata.get('evidence_fingerprint') or ''),
        )
        if duplicate is not None:
            return self._from_row(duplicate)

        case = ClientOutcomeDisputeCase(
            dispute_id=f'dispute:{uuid4().hex}',
            tenant_id=tenant_id,
            business_id=business_id,
            order_id=order_id,
            lead_id=lead_id,
            billable_record_id=billable_record_id,
            opened_at=now,
            opened_by=opened_by,
            reason_code=reason_code,
            status='open',
            notes=notes,
            metadata=classification_metadata,
        )
        self._dispute_store.save(case)
        return case

    def get_case(self, dispute_id: str) -> ClientOutcomeDisputeCase | None:
        row = self._dispute_store.get(dispute_id)
        if not row:
            return None
        return self._from_row(row)

    def accept_and_reverse(
        self,
        *,
        now: datetime,
        case: ClientOutcomeDisputeCase,
        original_record: BillableClientRecord,
        reversal_amount: float | None = None,
    ) -> ClientOutcomeDisputeResolutionResult:
        existing = self._reversal_store.find_by_original_record(
            tenant_id=case.tenant_id,
            original_billable_record_id=original_record.record_id,
        )
        if existing is not None:
            amount = float(existing.get('amount') or 0.0)
            currency = str(existing.get('currency') or original_record.currency)
            reversed_case = case if case.status == 'reversed' else replace(case, status='reversed', resolution_code='accepted_with_reversal')
            self._dispute_store.save(reversed_case)
            negative_record = BillableClientRecord(
                record_id=str(existing.get('negative_record_id') or f"{original_record.record_id}:reversal"),
                tenant_id=case.tenant_id,
                business_id=case.business_id,
                order_id=case.order_id,
                lead_id=case.lead_id,
                package_id=original_record.package_id,
                verified_at=now,
                unit_price=-abs(amount),
                currency=currency,
                quantity=1,
                metadata={**original_record.normalized_metadata(), 'reversal_of': original_record.record_id, 'reversal_reason_code': case.reason_code, 'replayed_reversal': True},
            )
            return ClientOutcomeDisputeResolutionResult(
                dispute=reversed_case,
                negative_record=negative_record,
                reversal_payload={
                    'reversal_id': str(existing['reversal_id']),
                    'negative_record_id': negative_record.record_id,
                    'amount': amount,
                    'currency': currency,
                    'partial_reversal': abs(float(amount) - abs(float(original_record.amount))) > 1e-9,
                    'replayed_reversal': True,
                },
            )

        window = self._refund_window_policy.evaluate(now=now, record=original_record)
        if not window.allowed:
            expired = replace(case, status='expired', resolution_code=window.reason_code)
            self._dispute_store.save(expired)
            return ClientOutcomeDisputeResolutionResult(dispute=expired, negative_record=None, reversal_payload=None)

        negative_record, reversal = self._negative_usage_builder.build_negative_record(
            now=now,
            original=original_record,
            reason_code=case.reason_code,
            amount=reversal_amount,
        )
        reversed_case = replace(case, status='reversed', resolution_code='accepted_with_reversal')
        self._dispute_store.save(reversed_case)
        self._reversal_store.save(
            {
                'reversal_id': reversal.reversal_id,
                'tenant_id': reversal.tenant_id,
                'business_id': reversal.business_id,
                'order_id': reversal.order_id,
                'lead_id': reversal.lead_id,
                'original_billable_record_id': reversal.original_billable_record_id,
                'negative_record_id': reversal.negative_record_id,
                'created_at': reversal.created_at.isoformat(),
                'reason_code': reversal.reason_code,
                'amount': reversal.amount,
                'currency': reversal.currency,
                'metadata': dict(reversal.metadata),
            }
        )
        return ClientOutcomeDisputeResolutionResult(
            dispute=reversed_case,
            negative_record=negative_record,
            reversal_payload={
                'reversal_id': reversal.reversal_id,
                'negative_record_id': reversal.negative_record_id,
                'amount': reversal.amount,
                'currency': reversal.currency,
                'partial_reversal': abs(float(reversal.amount) - abs(float(original_record.amount))) > 1e-9,
            },
        )

    def list_order_disputes(self, *, tenant_id: str, order_id: str) -> tuple[dict[str, object], ...]:
        return self._dispute_store.list_for_order(tenant_id=tenant_id, order_id=order_id)

    def list_order_reversals(self, *, tenant_id: str, order_id: str) -> tuple[dict[str, object], ...]:
        return self._reversal_store.list_for_order(tenant_id=tenant_id, order_id=order_id)

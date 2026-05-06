from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Sequence

from billing.client_outcome_billable_cap_policy import ClientOutcomeBillableCapPolicy
from billing.client_outcome_invoice_aggregator import ClientOutcomeInvoiceAggregator
from billing.client_outcome_package_progress import ClientOutcomePackageProgressCalculator
from billing.client_outcome_usage_ledger import ClientOutcomeUsageAppender, ClientOutcomeUsageLedger
from economics.client_outcome_economic_calculator import ClientOutcomeEconomicCalculator
from economics.client_outcome_economic_snapshot import ClientOutcomeEconomicSnapshot
from lead_outcomes.client_outcome_contract import BillableClientRecord, ClientOutcomeOrder

CANON_CLIENT_OUTCOME_REVENUE_CONTROL_SERVICE = True


@dataclass(frozen=True, slots=True)
class ClientOutcomeRevenueControlResult:
    appended_record_ids: tuple[str, ...]
    rejected_record_ids: tuple[str, ...]
    invoice_line_ids: tuple[str, ...]
    economic_snapshot: ClientOutcomeEconomicSnapshot
    billable_clients: int
    verified_clients: int


class ClientOutcomeRevenueControlService:
    def __init__(self, *, usage_ledger: ClientOutcomeUsageLedger, usage_appender: ClientOutcomeUsageAppender, progress_calculator: ClientOutcomePackageProgressCalculator, billable_cap_policy: ClientOutcomeBillableCapPolicy, invoice_aggregator: ClientOutcomeInvoiceAggregator, economic_calculator: ClientOutcomeEconomicCalculator) -> None:
        self._usage_ledger = usage_ledger
        self._usage_appender = usage_appender
        self._progress_calculator = progress_calculator
        self._billable_cap_policy = billable_cap_policy
        self._invoice_aggregator = invoice_aggregator
        self._economic_calculator = economic_calculator

    def process(self, *, now: datetime, order: ClientOutcomeOrder, verified_clients: int, existing_billable_records: Sequence[BillableClientRecord], new_records: Iterable[BillableClientRecord], acquisition_cost: float) -> ClientOutcomeRevenueControlResult:
        existing_records = tuple(existing_billable_records)
        progress = self._progress_calculator.calculate(order=order, verified_clients=verified_clients, billable_clients=sum(int(item.quantity) for item in existing_records))
        appended_ids: list[str] = []
        rejected_ids: list[str] = []
        accepted_records = list(existing_records)
        for record in new_records:
            decision = self._billable_cap_policy.evaluate(progress=progress, record=record)
            if not decision.allowed:
                rejected_ids.append(record.record_id)
                continue
            if self._usage_appender.append(record):
                appended_ids.append(record.record_id)
                accepted_records.append(record)
                progress = self._progress_calculator.calculate(order=order, verified_clients=verified_clients, billable_clients=sum(int(item.quantity) for item in accepted_records))
            else:
                rejected_ids.append(record.record_id)
        invoice_lines = self._invoice_aggregator.aggregate(now=now, records=accepted_records)
        snapshot = self._economic_calculator.calculate(tenant_id=order.tenant_id, business_id=order.business_id, order_id=order.order_id, package_id=order.package.package_id, verified_clients=verified_clients, billable_records=accepted_records, acquisition_cost=acquisition_cost, currency=order.package.currency)
        return ClientOutcomeRevenueControlResult(appended_record_ids=tuple(appended_ids), rejected_record_ids=tuple(rejected_ids), invoice_line_ids=tuple(item.invoice_line_id for item in invoice_lines), economic_snapshot=snapshot, billable_clients=snapshot.billable_clients, verified_clients=snapshot.verified_clients)

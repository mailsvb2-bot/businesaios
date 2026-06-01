from __future__ import annotations

from datetime import UTC, datetime

from billing.client_outcome_billable_cap_policy import ClientOutcomeBillableCapPolicy
from billing.client_outcome_invoice_aggregator import ClientOutcomeInvoiceAggregator
from billing.client_outcome_package_progress import ClientOutcomePackageProgressCalculator
from billing.client_outcome_revenue_control_service import ClientOutcomeRevenueControlService
from billing.client_outcome_usage_ledger import ClientOutcomeUsageAppender, ClientOutcomeUsageLedger
from economics.client_outcome_economic_calculator import ClientOutcomeEconomicCalculator
from lead_outcomes.client_outcome_contract import BillableClientRecord, ClientOutcomeOrder, ClientOutcomePackage


def test_client_outcome_revenue_stress_smoke() -> None:
    now = datetime(2026, 4, 13, 12, 0, 0, tzinfo=UTC)
    order = ClientOutcomeOrder(
        order_id='order-stress',
        tenant_id='tenant-1',
        business_id='biz-1',
        package=ClientOutcomePackage(package_id='clients-1000', label='1000 clients', requested_clients=1000, price_per_verified_client=10.0),
        created_at=now,
    )
    ledger = ClientOutcomeUsageLedger()
    service = ClientOutcomeRevenueControlService(
        usage_ledger=ledger,
        usage_appender=ClientOutcomeUsageAppender(ledger=ledger),
        progress_calculator=ClientOutcomePackageProgressCalculator(),
        billable_cap_policy=ClientOutcomeBillableCapPolicy(),
        invoice_aggregator=ClientOutcomeInvoiceAggregator(),
        economic_calculator=ClientOutcomeEconomicCalculator(),
    )
    records = tuple(
        BillableClientRecord(
            record_id=f'billable:{i}',
            tenant_id='tenant-1',
            business_id='biz-1',
            order_id='order-stress',
            lead_id=f'lead:{i}',
            package_id='clients-1000',
            verified_at=now,
            unit_price=10.0,
            currency='EUR',
        )
        for i in range(1000)
    )
    result = service.process(
        now=now,
        order=order,
        verified_clients=1000,
        existing_billable_records=(),
        new_records=records,
        acquisition_cost=2500.0,
    )
    assert len(result.appended_record_ids) == 1000
    assert result.billable_clients == 1000
    assert result.economic_snapshot.billed_revenue == 10000.0
    assert result.economic_snapshot.gross_margin == 7500.0

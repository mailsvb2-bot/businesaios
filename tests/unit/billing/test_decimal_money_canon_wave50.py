from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from billing.billable_event import BillableEvent
from billing.client_outcome_invoice_aggregator import ClientOutcomeInvoiceAggregator
from billing.client_outcome_negative_usage_builder import (
    ClientOutcomeNegativeUsageBuilder,
)
from billing.invoice_builder import InvoiceBuilder
from billing.invoice_event_mapper import InvoiceEventMapper
from billing.money import (
    amounts_equal,
    decimal_to_minor_units,
    money_decimal,
    quantity_times_minor_units,
    sum_money,
    to_minor_units,
)
from billing.outcome_tariff import OutcomeTariff
from billing.plan_contract import BillingPlanSpec, PlanRateCardItem
from billing.usage_meter import InMemoryUsageMeter, UsageRecord
from lead_outcomes.client_outcome_contract import BillableClientRecord
from tenancy.tenant_contract import TenantPlan
from tenancy.tenant_quota_guard import QuotaDimension, TenantQuotaGuard


def _record(*, record_id: str, unit_price: float, quantity: int = 1) -> BillableClientRecord:
    return BillableClientRecord(
        record_id=record_id,
        tenant_id="tenant-a",
        business_id="business-a",
        order_id="order-a",
        lead_id=f"lead-{record_id}",
        package_id="package-a",
        verified_at=datetime(2026, 7, 27, tzinfo=UTC),
        unit_price=unit_price,
        currency="RUB",
        quantity=quantity,
    )


def test_decimal_money_helpers_use_half_up_and_exact_minor_units() -> None:
    assert money_decimal("2.675") == Decimal("2.68")
    assert to_minor_units("2.675") == 268
    assert decimal_to_minor_units(Decimal("-2.675"), allow_negative=True) == -268
    assert sum_money(("0.10", "0.10", "0.10")) == Decimal("0.30")
    assert quantity_times_minor_units("2.675", 100) == 268
    assert amounts_equal(0.1 + 0.2, "0.30")


def test_invoice_builder_sums_three_tenths_exactly() -> None:
    invoice = InvoiceBuilder().build(
        [
            BillableEvent("lead-1", "conversion", 0.10, "RUB"),
            BillableEvent("lead-2", "conversion", 0.10, "RUB"),
            BillableEvent("lead-3", "conversion", 0.10, "RUB"),
        ],
        invoice_id="invoice-1",
    )
    assert invoice["totals"] == {"RUB": 0.3}
    assert to_minor_units(invoice["totals"]["RUB"]) == 30


def test_usage_meter_and_quota_guard_accumulate_decimal_quantities() -> None:
    meter = InMemoryUsageMeter()
    for index in range(3):
        meter.record(
            UsageRecord(
                tenant_id="tenant-a",
                meter_key="api_requests",
                quantity=0.1,
                idempotency_key=f"usage-{index}",
            )
        )
    assert meter.total(tenant_id="tenant-a", meter_key="api_requests") == 0.3

    guard = TenantQuotaGuard()
    for _ in range(3):
        verdict = guard.consume(
            tenant_id="tenant-a",
            dimension=QuotaDimension.DAILY_BUDGET.value,
            amount=0.1,
        )
        assert verdict.allowed
    assert guard.snapshot(tenant_id="tenant-a")["daily_budget"] == 0.3


def test_invoice_event_mapper_rounds_money_once_not_with_binary_float() -> None:
    plan = BillingPlanSpec(
        plan_id=TenantPlan.STARTER,
        display_name="Starter",
        rate_card=(
            PlanRateCardItem(
                meter_key="api_requests",
                unit_price=2.675,
                currency="RUB",
            ),
        ),
    )
    line = InvoiceEventMapper().build_line_item(
        record=UsageRecord(
            tenant_id="tenant-a",
            meter_key="api_requests",
            quantity=1,
        ),
        plan=plan,
    )
    assert line is not None
    assert line.amount == 2.68
    assert to_minor_units(line.amount) == 268


def test_outcome_invoice_aggregation_and_reversal_are_exact() -> None:
    records = (
        _record(record_id="1", unit_price=0.1),
        _record(record_id="2", unit_price=0.1),
        _record(record_id="3", unit_price=0.1),
    )
    lines = ClientOutcomeInvoiceAggregator().aggregate(
        now=datetime(2026, 7, 27, tzinfo=UTC),
        records=records,
    )
    assert len(lines) == 1
    assert lines[0].amount == 0.3

    original = _record(record_id="refund", unit_price=2.675)
    negative, reversal = ClientOutcomeNegativeUsageBuilder().build_negative_record(
        now=datetime(2026, 7, 27, tzinfo=UTC),
        original=original,
        reason_code="customer_refund",
        amount=1.005,
    )
    assert reversal.amount == 1.01
    assert negative.amount == -1.01


def test_conversion_tariff_uses_decimal_half_up() -> None:
    tariff = OutcomeTariff(conversion_fee_rate=0.1)
    assert tariff.price_for("conversion", revenue_amount=26.75) == 2.68


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, "bad"])
def test_money_boundary_rejects_invalid_values(value: object) -> None:
    with pytest.raises(ValueError):
        money_decimal(value)


def test_money_primitive_rejects_invalid_ranges_and_minor_unit_types() -> None:
    from billing.money import from_minor_units, quantity_decimal, rate_decimal, ratio_decimal

    assert from_minor_units(123) == Decimal("1.23")
    assert rate_decimal("0.1234567") == Decimal("0.123457")
    assert quantity_decimal("1.2345678") == Decimal("1.234568")
    assert ratio_decimal("0.5") == Decimal("0.500000")
    for value in (-1, "1.1"):
        with pytest.raises(ValueError):
            ratio_decimal(value)
    with pytest.raises(ValueError, match="must be an integer"):
        from_minor_units(True)
    with pytest.raises(ValueError, match="must be an integer"):
        quantity_times_minor_units(1, True)
    with pytest.raises(ValueError, match="currency is required"):
        BillableEvent("lead", "conversion", 1, " ")

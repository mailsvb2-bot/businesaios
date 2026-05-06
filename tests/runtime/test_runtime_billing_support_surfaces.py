from __future__ import annotations

from observability.slo_contract import SLIKind
from observability.tenant_metrics_registry import MetricAggregation, TenantMetricsRegistry
from runtime.monetization import MonetizationPlan, MonetizationService, TaxContext, UsageInvoiceRequest
from runtime.queue import InMemoryJobStore, JobDispatchRequest, JobDispatcher
from tenancy.tenant_billing_scope import BillingMode, TenantBillingScope
from tenancy.tenant_quota_guard import QuotaDimension, TenantQuotaGuard


def test_runtime_billing_support_surfaces_cover_real_owner_seams() -> None:
    monetization = MonetizationService()
    monetization.register_plan(
        MonetizationPlan(
            plan_id="growth",
            display_name="Growth",
            currency="EUR",
            interval="monthly",
            amount_minor=2500,
            included_usage={"connector_calls": 2.0},
            included_seats=1,
        )
    )
    invoice = monetization.build_usage_invoice(
        UsageInvoiceRequest(
            tenant_id="tenant-a",
            user_id="user-1",
            plan_id="growth",
            metered_usage={"connector_calls": 5.0},
            seat_count=2,
            meter_prices={"connector_calls": 1.75},
            seat_price=8.0,
            tax_context=TaxContext(country_code="NL", is_business_customer=False),
        )
    )
    assert invoice.subtotal_minor == 2500 + 525 + 800
    assert invoice.tax_minor == 803
    assert invoice.total_minor == 4628

    dispatcher = JobDispatcher(store=InMemoryJobStore())
    request = JobDispatchRequest(
        tenant_id="tenant-a",
        job_id="billing--invoice_issue--tenant-a--2026-04-10",
        queue_name="billing",
        job_type="billing.invoice_issue",
        payload={"invoice_id": invoice.invoice_id},
        dedupe_key="billing--invoice_issue--tenant-a--2026-04-10",
    )
    first = dispatcher.dispatch(request)
    second = dispatcher.dispatch(request)
    assert first.accepted is True
    assert second.accepted is True
    assert second.reason == "dedupe_existing"

    metrics = TenantMetricsRegistry()
    metrics.inc(tenant_id="tenant-a", metric_name="billing_invoices_total", amount=1.0, labels={"currency": "EUR"})
    metrics.emit(tenant_id="tenant-a", metric_name="billing_queue_latency_ms", kind=SLIKind.LATENCY_P95_MS, value=120.0, aggregation=MetricAggregation.P95)
    snapshot = metrics.snapshot(tenant_id="tenant-a")
    assert snapshot["billing_invoices_total"]["value"] == 1.0
    assert snapshot["billing_invoices_total"]["labels"]["currency"] == "EUR"
    assert snapshot["billing_queue_latency_ms"]["aggregation"] is MetricAggregation.P95

    billing_scope = TenantBillingScope(
        tenant_id="tenant-a",
        mode=BillingMode.POSTPAID,
        currency="EUR",
        meter_prices={"connector_calls": 1.75},
    )
    assert billing_scope.estimate_charge(meter_name="connector_calls", quantity=3.0) == 5.25

    quota_guard = TenantQuotaGuard()
    allowed = quota_guard.consume(tenant_id="tenant-a", dimension=QuotaDimension.CONNECTOR_CALLS_PER_HOUR.value, amount=3.0)
    assert allowed.allowed is True
    assert quota_guard.snapshot(tenant_id="tenant-a")[QuotaDimension.CONNECTOR_CALLS_PER_HOUR.value] == 3.0

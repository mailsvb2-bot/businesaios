from __future__ import annotations

from billing.monetization_adapter import BillingMonetizationAdapter
from billing.plan_contract import BillingMeterKey, BillingPlanSpec, PlanRateCardItem
from billing.revenue_os_bridge import BillingRevenueOSBridge
from billing.scheduler.queue_bridge import BillingQueueJobSpec, dispatch_billing_job
from runtime.monetization import MonetizationService
from runtime.queue import InMemoryJobStore, JobDispatcher
from tenancy.tenant_contract import TenantPlan


def test_billing_surfaces_bind_to_runtime_owner_packages_without_fake_imports() -> None:
    plan = BillingPlanSpec(
        plan_id=TenantPlan.GROWTH,
        display_name="Growth",
        rate_card=(
            PlanRateCardItem(
                meter_key=BillingMeterKey.CONNECTOR_CALLS,
                unit_price=2.0,
                currency="EUR",
                included_units=2.0,
                unit_name="call",
            ),
        ),
        metadata={"base_amount": 49.0, "interval": "monthly", "included_seats": 1, "trial_days": 7},
    )

    adapter = BillingMonetizationAdapter()
    invoice = adapter.build_usage_invoice(
        service=MonetizationService(),
        tenant_id="tenant-b",
        user_id="user-2",
        plan=plan,
        metered_usage={BillingMeterKey.CONNECTOR_CALLS: 4.0},
        seat_count=2,
        meter_prices={BillingMeterKey.CONNECTOR_CALLS: 2.0},
        seat_price=6.0,
        country_code="DE",
        subscription_id="sub-1",
    )
    assert invoice.subtotal_minor == 4900 + 400 + 600
    assert invoice.tax_minor == 1121
    assert invoice.total_minor == 7021

    bridge = BillingRevenueOSBridge()
    revenue_plan = bridge.subscription_plan_from_spec(plan)
    paywalls = bridge.default_paywall_variants((plan,))
    assert revenue_plan.plan_id == "growth"
    assert revenue_plan.price.currency == "EUR"
    assert len(paywalls) == 2

    dispatcher = JobDispatcher(store=InMemoryJobStore())
    dispatched = dispatch_billing_job(
        dispatcher=dispatcher,
        spec=BillingQueueJobSpec(
            tenant_id="tenant-b",
            job_name="invoice_issue",
            run_key="2026-04-10",
            payload={"invoice_id": invoice.invoice_id},
        ),
    )
    assert dispatched.accepted is True
    assert dispatched.request.job_type == "billing.invoice_issue"
    assert dispatched.request.payload["billing_lineage_root"] == f"billing:invoice:{invoice.invoice_id}"

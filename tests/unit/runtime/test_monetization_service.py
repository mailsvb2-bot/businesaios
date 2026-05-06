from __future__ import annotations

from billing.monetization_adapter import BillingMonetizationAdapter
from billing.plan_contract import BillingMeterKey, BillingPlanSpec, PlanRateCardItem
from runtime.monetization import MonetizationPlan, MonetizationService, TaxContext, UsageInvoiceRequest
from tenancy import TenantPlan


def test_monetization_service_builds_invoice_dashboard_and_reverse_charge() -> None:
    service = MonetizationService()
    service.register_plan(
        MonetizationPlan(
            plan_id='pro',
            display_name='Pro',
            currency='EUR',
            interval='monthly',
            amount_minor=1900,
            included_usage={BillingMeterKey.CONNECTOR_CALLS: 2.0},
            included_seats=1,
        )
    )
    sub = service.activate_subscription(tenant_id='tenant-a', user_id='user-1', plan_id='pro')
    invoice = service.build_usage_invoice(
        UsageInvoiceRequest(
            tenant_id='tenant-a',
            user_id='user-1',
            plan_id='pro',
            metered_usage={BillingMeterKey.CONNECTOR_CALLS: 5.0},
            seat_count=3,
            meter_prices={BillingMeterKey.CONNECTOR_CALLS: 1.5},
            seat_price=5.0,
            tax_context=TaxContext(country_code='NL', is_business_customer=True, tax_id='NL12345678B01'),
            subscription_id=sub.subscription_id,
        )
    )
    assert invoice.subtotal_minor == 1900 + 450 + 1000
    assert invoice.tax_minor == 0
    assert invoice.total_minor == 3350
    assert invoice.metadata['reverse_charge_applied'] is True

    service.record_refund(tenant_id='tenant-a', user_id='user-1', amount_minor=350, currency='EUR', reason='goodwill')
    service.record_chargeback(tenant_id='tenant-a', user_id='user-1', amount_minor=200, currency='EUR', reason='dispute')
    dashboard = service.build_dashboard_snapshot(tenant_id='tenant-a', currency='EUR')
    assert dashboard.gross_revenue_minor == 3350
    assert dashboard.refunded_minor == 350
    assert dashboard.chargeback_minor == 200
    assert dashboard.net_revenue_minor == 2800
    assert dashboard.active_subscriptions == 1


def test_billing_monetization_adapter_translates_plan_and_usage() -> None:
    adapter = BillingMonetizationAdapter()
    service = MonetizationService()
    plan = BillingPlanSpec(
        plan_id=TenantPlan.ENTERPRISE,
        display_name='Enterprise',
        rate_card=(
            PlanRateCardItem(
                meter_key=BillingMeterKey.CONNECTOR_CALLS,
                unit_price=2.0,
                currency='USD',
                included_units=3.0,
                unit_name='call',
            ),
        ),
        metadata={'base_amount': 99.0, 'interval': 'monthly', 'included_seats': 2},
    )
    invoice = adapter.build_usage_invoice(
        service=service,
        tenant_id='tenant-b',
        user_id='user-2',
        plan=plan,
        metered_usage={BillingMeterKey.CONNECTOR_CALLS: 4.0},
        seat_count=4,
        meter_prices={BillingMeterKey.CONNECTOR_CALLS: 2.0},
        seat_price=7.5,
        country_code='US',
    )
    assert invoice.subtotal_minor == 9900 + 200 + 1500
    assert invoice.tax_minor == 0
    assert invoice.total_minor == 11600

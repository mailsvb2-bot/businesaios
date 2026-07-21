from __future__ import annotations

from datetime import UTC, datetime
from math import inf, nan

import pytest

from billing.monetization_adapter import BillingMonetizationAdapter
from billing.plan_contract import BillingPlanSpec, PlanQuotaLimit, PlanRateCardItem
from billing.revenue_os_bridge import BillingRevenueOSBridge
from runtime.monetization import MonetizationService
from tenancy.tenant_contract import TenantPlan

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _plan(**changes) -> BillingPlanSpec:
    values = {
        "plan_id": TenantPlan.GROWTH,
        "display_name": " Growth ",
        "version": " v2 ",
        "quota_limits": (PlanQuotaLimit(dimension="actions", limit=100),),
        "rate_card": (
            PlanRateCardItem(
                meter_key="actions",
                unit_price=0.5,
                currency="USD",
                included_units=2,
            ),
        ),
        "features": {"exports": True, "audit": False},
        "metadata": {
            "base_amount": 10.5,
            "interval": "monthly",
            "included_seats": 2,
            "trial_days": 7,
            "tier": " Growth ",
            "recommended": True,
            "nested": {"value": 1},
        },
        "created_at": NOW,
    }
    values.update(changes)
    return BillingPlanSpec(**values)


def _metadata(**changes):
    values = dict(_plan().metadata)
    values.update(changes)
    return values


def test_monetization_plan_translation_is_strict_and_deeply_snapshotted() -> None:
    source = _plan()
    runtime_plan = BillingMonetizationAdapter().plan_from_spec(source)

    assert runtime_plan.plan_id == "growth"
    assert runtime_plan.currency == "USD"
    assert runtime_plan.interval == "monthly"
    assert runtime_plan.amount_minor == 1050
    assert runtime_plan.included_usage == {"actions": 2.0}
    assert runtime_plan.included_seats == 2
    runtime_plan.metadata["nested"]["value"] = 9
    assert source.metadata["nested"]["value"] == 1

    weekly = BillingMonetizationAdapter().plan_from_spec(
        _plan(metadata=_metadata(interval=" WEEKLY ", base_amount=0, included_seats=0))
    )
    assert weekly.interval == "weekly"
    assert weekly.amount_minor == 0
    assert weekly.included_seats == 0

    without_rate = BillingMonetizationAdapter().plan_from_spec(_plan(rate_card=()))
    assert without_rate.currency == "USD"
    assert without_rate.included_usage == {}


def test_monetization_plan_rejects_coercible_or_ambiguous_metadata() -> None:
    adapter = BillingMonetizationAdapter()
    with pytest.raises(ValueError, match="BillingPlanSpec"):
        adapter.plan_from_spec(object())

    invalid_metadata = [
        _metadata(base_amount=True),
        _metadata(base_amount="10"),
        _metadata(base_amount=-1),
        _metadata(base_amount=nan),
        _metadata(base_amount=inf),
        _metadata(base_amount=1.234),
        _metadata(interval=1),
        _metadata(interval=" "),
        _metadata(interval="quarterly"),
        _metadata(included_seats=True),
        _metadata(included_seats="2"),
        _metadata(included_seats=-1),
    ]
    for metadata in invalid_metadata:
        with pytest.raises(ValueError):
            adapter.plan_from_spec(_plan(metadata=metadata))


def test_usage_invoice_boundary_validates_before_registering_or_billing() -> None:
    service = MonetizationService()
    invoice = BillingMonetizationAdapter().build_usage_invoice(
        service=service,
        tenant_id=" tenant-a ",
        user_id=" user-a ",
        plan=_plan(),
        metered_usage={" actions ": 4},
        seat_count=3,
        meter_prices={" actions ": 0.5},
        seat_price=1,
        country_code=" us ",
        is_business_customer=False,
        tax_id=" tax-a ",
        subscription_id=" sub-a ",
    )

    assert invoice.tenant_id == "tenant-a"
    assert invoice.user_id == "user-a"
    assert invoice.subtotal_minor == 1250
    assert invoice.total_minor == 1250
    assert service.store.plans["growth"].amount_minor == 1050


def test_usage_invoice_rejects_malformed_boundary_values() -> None:
    adapter = BillingMonetizationAdapter()
    base = {
        "service": MonetizationService(),
        "tenant_id": "tenant-a",
        "user_id": "user-a",
        "plan": _plan(),
        "metered_usage": {"actions": 1},
    }
    invalid = [
        {"tenant_id": 1},
        {"tenant_id": " "},
        {"user_id": 1},
        {"user_id": " "},
        {"metered_usage": []},
        {"metered_usage": {1: 1}},
        {"metered_usage": {" ": 1}},
        {"metered_usage": {"a": 1, " a ": 2}},
        {"metered_usage": {"a": True}},
        {"metered_usage": {"a": "1"}},
        {"metered_usage": {"a": -1}},
        {"metered_usage": {"a": nan}},
        {"meter_prices": []},
        {"meter_prices": {"a": inf}},
        {"seat_count": True},
        {"seat_count": "1"},
        {"seat_count": -1},
        {"seat_price": True},
        {"seat_price": "1"},
        {"seat_price": -1},
        {"country_code": 1},
        {"country_code": " "},
        {"is_business_customer": 1},
        {"tax_id": 1},
        {"tax_id": " "},
        {"subscription_id": 1},
        {"subscription_id": " "},
    ]
    for changes in invalid:
        with pytest.raises(ValueError):
            adapter.build_usage_invoice(**(base | changes))


def test_revenue_plan_translation_preserves_canonical_intervals_and_zero_seats() -> None:
    bridge = BillingRevenueOSBridge()
    monthly = bridge.subscription_plan_from_spec(_plan(metadata=_metadata(included_seats=0)))
    assert monthly.price.amount == 10.5
    assert monthly.price.billing_period_days == 30
    assert monthly.price.trial_days == 7
    assert monthly.tier == "growth"
    assert monthly.feature_flags == ("exports",)
    assert monthly.seats_included == 0
    assert monthly.recommended is True

    weekly = bridge.subscription_plan_from_spec(_plan(metadata=_metadata(interval="weekly")))
    yearly = bridge.subscription_plan_from_spec(_plan(metadata=_metadata(interval="yearly")))
    assert weekly.price.billing_period_days == 7
    assert yearly.price.billing_period_days == 365

    without_rate = bridge.subscription_plan_from_spec(_plan(rate_card=()))
    assert without_rate.price.currency == "USD"


def test_revenue_plan_rejects_coercible_metadata() -> None:
    bridge = BillingRevenueOSBridge()
    with pytest.raises(ValueError, match="BillingPlanSpec"):
        bridge.subscription_plan_from_spec(object())

    invalid = [
        _metadata(base_amount=True),
        _metadata(base_amount="10"),
        _metadata(base_amount=-1),
        _metadata(base_amount=nan),
        _metadata(base_amount=inf),
        _metadata(base_amount=1.234),
        _metadata(interval=1),
        _metadata(interval=" "),
        _metadata(interval="quarterly"),
        _metadata(tier=1),
        _metadata(tier=" "),
        _metadata(trial_days=True),
        _metadata(trial_days="7"),
        _metadata(trial_days=-1),
        _metadata(included_seats=True),
        _metadata(included_seats="1"),
        _metadata(included_seats=-1),
        _metadata(recommended=1),
    ]
    for metadata in invalid:
        with pytest.raises(ValueError):
            bridge.subscription_plan_from_spec(_plan(metadata=metadata))


def test_paywall_variants_require_typed_plans_and_strict_trial_days() -> None:
    bridge = BillingRevenueOSBridge()
    variants = bridge.default_paywall_variants((_plan(),))
    assert len(variants) == 2
    assert all(item.emphasizes_trial for item in variants)

    no_trial = bridge.default_paywall_variants(plan for plan in (_plan(metadata=_metadata(trial_days=0)),))
    assert not any(item.emphasizes_trial for item in no_trial)

    for invalid in (None, [], "plans", {"plan": _plan()}, (object(),)):
        with pytest.raises(ValueError):
            bridge.default_paywall_variants(invalid)
    for trial_days in (True, "7", -1):
        with pytest.raises(ValueError):
            bridge.default_paywall_variants((_plan(metadata=_metadata(trial_days=trial_days)),))


def test_revenue_snapshot_is_exact_aware_and_finite() -> None:
    bridge = BillingRevenueOSBridge()
    snapshot = bridge.revenue_snapshot_from_metrics(
        observed_at=NOW,
        visitors=10,
        trials_started=4,
        conversions=2,
        retained_subscribers=8,
        churned_subscribers=1,
        refunds=1,
        gross_revenue=100.5,
        net_revenue=-5.25,
        acquisition_spend=20,
        active_subscribers=9,
        trial_subscribers=3,
    )
    assert snapshot.observed_at is NOW
    assert snapshot.visitors == 10
    assert snapshot.net_revenue == -5.25


def test_revenue_snapshot_rejects_coercion_non_finite_and_negative_counts() -> None:
    bridge = BillingRevenueOSBridge()
    base = {
        "observed_at": NOW,
        "visitors": 10,
        "trials_started": 4,
        "conversions": 2,
        "retained_subscribers": 8,
        "churned_subscribers": 1,
        "refunds": 1,
        "gross_revenue": 100.5,
        "net_revenue": 80.0,
        "acquisition_spend": 20.0,
        "active_subscribers": 9,
        "trial_subscribers": 3,
    }
    invalid = [
        {"observed_at": datetime(2026, 1, 1)},
        {"visitors": True},
        {"trials_started": "4"},
        {"conversions": -1},
        {"retained_subscribers": True},
        {"churned_subscribers": -1},
        {"refunds": "1"},
        {"gross_revenue": True},
        {"gross_revenue": -1},
        {"gross_revenue": nan},
        {"net_revenue": "1"},
        {"net_revenue": inf},
        {"acquisition_spend": -1},
        {"active_subscribers": True},
        {"trial_subscribers": -1},
    ]
    for changes in invalid:
        with pytest.raises(ValueError):
            bridge.revenue_snapshot_from_metrics(**(base | changes))

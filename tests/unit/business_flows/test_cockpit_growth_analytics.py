from datetime import date
from types import SimpleNamespace as NS

import pytest

from application.business_flows import cockpit_growth_analytics as cga

AD = NS(connected_accounts=1, tracked_ads=2, impressions=100, clicks=5, leads=2, bookings=1, won=0,
        ctr_percent=5.0, date_from="2026-10-17", date_to="2026-10-23")
M = NS(amount_minor=150000, currency="RUB")
SNAP = NS(period_days=7, period_from=date(2026, 10, 17), period_to=date(2026, 10, 23),
          period_metrics=[NS(key="leads", value=3, meaning="m")], revenue=[M],
          what_worked=[NS(source="telegram", label="Telegram", outcomes=2)], attention=["a"],
          actions=[NS(title="t", reason="r", action_key="k")], advertising=AD, limitations=["x", "x"],
          journey=NS(leads=3, bookings=1, completed_bookings=1, paid_customers=1, reactivated_customers=0,
                     limitations=("booking_completion_unavailable",), verified_revenue_by_currency=[M],
                     attributed_revenue_by_currency=[], unattributed_revenue_by_currency=[M]))


def _b(role, ad=lambda d: AD):
    return cga.build(role=role, business_id="b", business_name="Студия", load_snapshot=lambda d: SNAP,
                     load_advertising=ad)


def test_full_view_for_ledger_roles():
    a = _b("owner")
    assert a.business_results_available and a.can_manage_promotions
    assert a.revenue[0].display == "1 500.00 RUB" and a.journey.completed_bookings == -1
    assert a.limitations == ("x",) and a.metrics == (("leads", 3, "m"),) and a.advertising.clicks == 5


def test_restricted_and_denied():
    a = _b("marketer")
    assert not a.business_results_available and a.can_manage_promotions and a.journey.leads is None
    assert a.limitations == ("business_results_restricted_for_role", "advertising_currency_unverified")

    def down(d):
        raise RuntimeError
    r = _b("analyst", down)
    assert r.limitations[-1] == "advertising_unavailable" and not r.can_manage_promotions and r.advertising is None
    with pytest.raises(PermissionError):
        _b("support")

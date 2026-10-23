from datetime import UTC, datetime
from enum import Enum
from types import SimpleNamespace as NS

import pytest

from application.business_flows import growth_cockpit as gc


class Src(Enum):
    YD = "yandex_direct"


NOW = datetime(2026, 10, 23, 22, 30, tzinfo=UTC)  # 01:30 next day in Moscow


def test_windows_follow_business_zone():
    z = gc.business_zone("Europe/Moscow")
    s, e = gc.today_window(zone=z, now=NOW)
    assert s.isoformat() == "2026-10-23T21:00:00+00:00" and e.isoformat() == "2026-10-24T21:00:00+00:00"
    s7, e7 = gc.window_for_days(zone=z, days=7, now=NOW)
    assert s7.isoformat() == "2026-10-17T21:00:00+00:00" and e7 == e
    with pytest.raises(ValueError):
        gc.window_for_days(zone=z, days=14, now=NOW)
    with pytest.raises(ValueError):
        gc.today_window(zone=z, now=datetime(2026, 1, 1))
    with pytest.raises(ValueError):
        gc.business_zone("Mars/Base")


def test_metrics_revenue_sources_money():
    e = NS(leads=5, qualified_leads=3, bookings=2, paid_customers=1,
           revenue_by_currency=[NS(amount_minor=150000, currency="RUB")],
           source_breakdown={"telegram": 2, Src.YD: 2, "vk": 0, "zzz": 1})
    assert [m.value for m in gc.metrics(e)] == [5, 3, 2, 1]
    assert gc.revenue(e)[0].amount_minor == 150000
    assert [(r.source, r.label) for r in gc.what_worked(e)] == [
        ("telegram", "Telegram"), ("yandex_direct", "Яндекс Директ"), ("zzz", "Источник клиентов")]
    assert gc.money_text(150000, "rub") == "1 500.00 RUB" and gc.money_text(5, "JPY") == "5 JPY"
    assert gc.money_text(1234, "KWD") == "1.234 KWD"
    with pytest.raises(ValueError):
        gc.utc("2026-10-01T00:00:00")


def _auth(status="active", exp="2026-12-01T00:00:00Z", receipt="r"):
    return NS(id="a1", status=status, consent_receipt=receipt, authorization_expires_at=exp,
              snapshot=NS(valid_until="2026-12-01T00:00:00Z"), hard_cap_minor=1000000, daily_cap_minor=100000,
              currency="RUB")


def test_economic_next_action_order():
    j = NS(reactivated_customers=2, sources=[NS(source="yandex_direct", paid_customers=3)])
    f = gc.economic_next_action
    assert f(open_slots=0, reactivation=[], authorizations=[], journey=j, now=NOW).action_key == "economic_open_slots"
    re = [NS(route_platform=None), NS(route_platform="telegram", candidate=NS(customer_id="c9"))]
    a = f(open_slots=2, reactivation=re, authorizations=[], journey=j, now=NOW)
    assert a.action_key == "economic_reactivation" and a.source_id == "c9" and "возвратов: 2" in a.reason
    a = f(open_slots=2, reactivation=[], authorizations=[_auth("revoked"), _auth(exp="2026-01-01T00:00:00Z"),
                                                        _auth(receipt=None), _auth()], journey=j, now=NOW)
    assert a.action_key == "economic_paid_acquisition" and "10 000.00 RUB" in a.reason and "клиентов: 3" in a.reason
    assert f(open_slots=2, reactivation=[], authorizations=[], journey=j, now=NOW) is None

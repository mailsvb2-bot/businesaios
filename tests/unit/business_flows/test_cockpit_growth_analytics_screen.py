from __future__ import annotations

from application.business_flows import bookings as bk
from application.business_flows import cockpit as cp
from application.business_flows import cockpit_growth_analytics as ga

NOW = 1_800_000_000_000
DAY = 86_400_000


def _snap() -> cp.Snapshot:
    slots = [
        bk.Slot("a", "Йога", NOW - DAY, 60, status="booked", customer_id="u1"),
        bk.Slot("b", "Йога", NOW - 20 * DAY, 60, status="booked", customer_id="u2"),
    ]
    return cp.Snapshot(all_slots=slots, now_ms=NOW)


def test_growth_analytics_screen_period_and_honest_limits() -> None:
    text, rows = cp.render(cp.parse("cpm:growth-an:7"), _snap(), is_owner=True)
    assert "7 дн." in text and "Записи: 1" in text and "платежей нет" in text
    assert "источники выручки не отслеживаются" in text
    assert "cpm:growth-an:30" in [cb for r in rows for _, cb in r]
    assert "Записи: 2" in cp.render(cp.parse("cpm:growth-an:30"), _snap(), is_owner=True)[0]
    assert "cpm:growth-an:7" in [
        cb for r in cp.render(cp.parse("cpm:growth"), _snap(), is_owner=True)[1] for _, cb in r
    ]


def test_restricted_role_hides_business_results() -> None:
    text = ga.screen(_snap(), role="marketer")
    assert "Записи" not in text and "недоступны для роли" in text

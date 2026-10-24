"""Owner growth analytics projection (port of donor cockpit_growth_analytics).

Pure: the caller passes the role, a growth snapshot (metrics/revenue/journey…) and an
advertising loader; roles without outcome-ledger access get the restricted view (ads only).
Nothing here reads stores, calls providers or writes.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from application.business_flows.customer_timeline_sources import can_view_attribution, can_view_outcomes
from application.business_flows.growth_cockpit import money_text

CANON_COCKPIT_GROWTH_ANALYTICS = True
SCHEMA_VERSION = "2026-09-07.v1"
PROMOTION_MANAGERS = frozenset({"owner", "administrator", "manager", "content_manager", "marketer"})
PROMOTION_VIEWERS = PROMOTION_MANAGERS | {"analyst"}


@dataclass(frozen=True, slots=True)
class GMoney:
    currency: str
    amount_minor: int
    display: str


@dataclass(frozen=True, slots=True)
class Advertising:
    connected_accounts: int
    tracked_ads: int
    impressions: int
    clicks: int
    leads: int
    bookings: int
    won: int
    ctr_percent: float


@dataclass(frozen=True, slots=True)
class Journey:
    leads: int | None
    bookings: int | None
    completed_bookings: int | None
    paid_customers: int | None
    reactivated_customers: int | None
    verified_revenue: tuple[GMoney, ...]
    attributed_revenue: tuple[GMoney, ...]
    unattributed_revenue: tuple[GMoney, ...]


@dataclass(frozen=True, slots=True)
class Analytics:
    schema_version: str
    business_id: str
    business_name: str
    period_days: int
    period_from: str
    period_to: str
    metrics: tuple[tuple[str, int, str], ...]
    revenue: tuple[GMoney, ...]
    sources: tuple[tuple[str, str, int], ...]
    attention: tuple[str, ...]
    actions: tuple[tuple[str, str, str], ...]
    advertising: Advertising | None
    journey: Journey
    limitations: tuple[str, ...]
    can_manage_promotions: bool
    business_results_available: bool


def gmoney(amount_minor: int, currency: str) -> GMoney:
    return GMoney(str(currency).upper(), int(amount_minor), money_text(int(amount_minor), currency))


def money_rows(values: Iterable[Any]) -> tuple[GMoney, ...]:
    return tuple(gmoney(int(v.amount_minor), str(v.currency)) for v in values)


def require_viewer(role: str) -> str:
    if str(role or "") not in PROMOTION_VIEWERS:
        raise PermissionError("promotion analytics requires owner, administrator, manager, "
                              "content manager, marketer or analyst role")
    return str(role)


def can_manage_promotions(role: str) -> bool:
    return str(role or "") in PROMOTION_MANAGERS


def can_view_business_results(role: str) -> bool:
    return can_view_outcomes(role) and can_view_attribution(role)


def advertising_summary(v: Any | None) -> Advertising | None:
    if v is None:
        return None
    return Advertising(int(v.connected_accounts), int(v.tracked_ads), int(v.impressions), int(v.clicks),
                       int(v.leads), int(v.bookings), int(v.won), float(v.ctr_percent))


_EMPTY_JOURNEY = Journey(None, None, None, None, None, (), (), ())


def restricted(*, role: str, business_id: str, business_name: str, period_days: int,
               load_advertising: Callable[[int], Any]) -> Analytics:
    limitations = ["business_results_restricted_for_role"]
    ad, p_from, p_to = None, "", ""
    try:
        ad = load_advertising(period_days)
        p_from, p_to = str(ad.date_from), str(ad.date_to)
        if int(ad.connected_accounts) > 0:
            limitations.append("advertising_currency_unverified")
    except (OSError, RuntimeError, ValueError):
        limitations.append("advertising_unavailable")
    return Analytics(SCHEMA_VERSION, business_id, str(business_name), int(period_days), p_from, p_to, (), (), (),
                     (), (), advertising_summary(ad), _EMPTY_JOURNEY, tuple(limitations),
                     can_manage_promotions(role), False)


def build(*, role: str, business_id: str, business_name: str, period_days: int = 7,
          load_snapshot: Callable[[int], Any], load_advertising: Callable[[int], Any]) -> Analytics:
    role = require_viewer(role)
    if not can_view_business_results(role):
        return restricted(role=role, business_id=business_id, business_name=business_name,
                          period_days=period_days, load_advertising=load_advertising)
    s = load_snapshot(period_days)
    j = s.journey
    completed = -1 if "booking_completion_unavailable" in tuple(j.limitations) else int(j.completed_bookings)
    return Analytics(
        SCHEMA_VERSION, business_id, str(business_name), int(s.period_days),
        s.period_from.isoformat(), s.period_to.isoformat(),
        tuple((m.key, int(m.value), m.meaning) for m in s.period_metrics),
        tuple(gmoney(int(r.amount_minor), str(r.currency)) for r in s.revenue),
        tuple((w.source, w.label, int(w.outcomes)) for w in s.what_worked),
        tuple(str(a) for a in s.attention),
        tuple((a.title, a.reason, a.action_key) for a in s.actions),
        advertising_summary(s.advertising),
        Journey(int(j.leads), int(j.bookings), completed, int(j.paid_customers), int(j.reactivated_customers),
                money_rows(j.verified_revenue_by_currency), money_rows(j.attributed_revenue_by_currency),
                money_rows(j.unattributed_revenue_by_currency)),
        tuple(dict.fromkeys(str(x) for x in s.limitations)),
        can_manage_promotions(role), True,
    )


_DAY_MS = 86_400_000
_LIMIT_TEXT = {
    "leads_period_unfiltered": "обращения — за всё время",
    "paid_customers_unavailable": "оплаты не привязаны к клиентам",
    "attribution_unavailable": "источники выручки не отслеживаются",
    "advertising_unavailable": "рекламных кабинетов нет",
    "business_results_restricted_for_role": "результаты бизнеса недоступны для роли",
}


def snapshot_from_cockpit(s: Any, *, period_days: int = 7) -> Any:
    """Donor-shaped snapshot from the port's own facts (sales, bookings, attendance, payments). No ad data."""
    from datetime import UTC, datetime
    from types import SimpleNamespace as NS

    from application.business_flows import admin as ad

    lo = s.now_ms - period_days * _DAY_MS
    booked = [x for x in s.all_slots if x.status == "booked" and lo <= x.starts_at_ms <= s.now_ms]
    att = getattr(s.series, "attendance", {}) or {}
    came = sum(1 for x in booked if att.get((x.slot_id, x.customer_id)) == "attended")
    leads = len(getattr(s.sales, "leads", {}) or {}) if s.sales is not None else 0
    pay = ad.payment_summary(s.admin) if s.admin is not None else {}
    money = [NS(amount_minor=r["net_minor"], currency=c) for c, r in sorted(pay.items())]
    lim = ("leads_period_unfiltered", "paid_customers_unavailable", "attribution_unavailable", "advertising_unavailable")
    day = lambda ms: datetime.fromtimestamp(ms / 1000, UTC).date()  # noqa: E731
    return NS(
        period_days=period_days, period_from=day(lo), period_to=day(s.now_ms),
        period_metrics=[NS(key="bookings", value=len(booked), meaning="Записи за период"),
                        NS(key="attended", value=came, meaning="Пришли")],
        revenue=money, what_worked=[], attention=[], actions=[], advertising=None, limitations=lim,
        journey=NS(leads=leads, bookings=len(booked), completed_bookings=came, paid_customers=0,
                   reactivated_customers=0, verified_revenue_by_currency=money,
                   attributed_revenue_by_currency=[], unattributed_revenue_by_currency=money, limitations=lim),
    )


def render_text(a: Analytics) -> str:
    lines = [f"📊 Аналитика роста · {a.period_days} дн. ({a.period_from} — {a.period_to})", ""]
    if a.business_results_available:
        j = a.journey
        lines.append(f"Обращения: {j.leads} · Записи: {j.bookings} · Пришли: {j.completed_bookings}")
        lines += [f"Выручка {m.currency}: {m.display}" for m in j.verified_revenue] or ["Выручка: платежей нет"]
    notes = [_LIMIT_TEXT.get(x, x) for x in a.limitations]
    return "\n".join(lines + ([""] + ["Ограничения: " + "; ".join(notes)] if notes else []))


def screen(s: Any, *, role: str = "owner", period_days: int = 7) -> str:
    snap = snapshot_from_cockpit(s, period_days=period_days)
    a = build(role=role, business_id="", business_name=s.business, period_days=period_days,
              load_snapshot=lambda _d: snap, load_advertising=lambda _d: (_ for _ in ()).throw(ValueError("none")))
    return render_text(a)


__all__ = ["CANON_COCKPIT_GROWTH_ANALYTICS", "Analytics", "build", "can_manage_promotions",
           "can_view_business_results", "render_text", "restricted", "screen", "snapshot_from_cockpit"]

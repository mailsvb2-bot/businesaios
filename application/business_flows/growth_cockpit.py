"""Owner growth cockpit: one deterministic "what to do now" queue (port of ClientPlatform growth_cockpit).

Pure projection over existing facts (sales_pipeline, bookings, event_series, business_admin).
Owns no facts, makes no provider calls; every action points to an existing cockpit screen.
Ad spend and source attribution are not recorded in this port, so they are reported as absent.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from application.business_flows import sales as sl

CANON_GROWTH_COCKPIT = True


@dataclass(frozen=True)
class Action:
    title: str
    reason: str
    cmd: str


def customer_work_actions(s: Any) -> list[Action]:
    """Donor _customer_work_actions: handoffs first, then overdue sales steps (lead order)."""
    st = s.sales
    if st is None:
        return []
    out = [
        Action(f"Подключиться: {x.name}", "Клиент ждёт ответа человека.", f"cpm:sales-lead:{x.lead_id}")
        for x in sl.ordered(st)
        if x.handoff_open and x.stage not in (sl.Stage.WON, sl.Stage.LOST)
    ]
    out += [
        Action(f"Шаг по {x.name}", f"Просрочено: {x.next_action}"[:120], f"cpm:sales-lead:{x.lead_id}")
        for x in sl.due_actions(st, now_ms=s.now_ms)
        if not x.handoff_open
    ]
    return out


def customer_action(s: Any, customer_id: str) -> Action | None:
    """Donor build_cockpit_customer_action_route/_customer_action: the one current action for this
    customer (their lead's handoff/overdue step, else an unmarked past visit). ``cmd`` is the route."""
    st = s.sales
    leads = {x.lead_id: x for x in sl.ordered(st)} if st is not None else {}
    for a in customer_work_actions(s):
        lead = leads.get(a.cmd.rsplit(":", 1)[-1])
        if lead is not None and lead.customer_id == customer_id:
            return a
    att = getattr(s.series, "attendance", {}) or {}
    if any(
        x.customer_id == customer_id and x.status == "booked" and x.starts_at_ms <= s.now_ms
        and (x.slot_id, customer_id) not in att
        for x in s.all_slots
    ):
        return Action("Отметить посещение", "Прошедшая запись без отметки.", "cpm:ev-conduct")
    return None


def action_queue(s: Any, *, limit: int = 5) -> tuple[Action, ...]:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 10:
        raise ValueError("owner action queue limit must be an integer between 1 and 10")
    actions = customer_work_actions(s)
    att = getattr(s.series, "attendance", {}) or {}
    unmarked = sum(
        1
        for x in s.all_slots
        if x.status == "booked" and x.starts_at_ms <= s.now_ms and (x.slot_id, x.customer_id) not in att
    )
    if unmarked:
        actions.append(Action("Отметить посещение", f"Без отметки: {unmarked}; от этого зависят follow-up.", "cpm:ev-conduct"))
    pending = [x for x in getattr(s.admin, "approvals", {}).values() if x.status == "pending"]
    if pending:
        actions.append(Action("Решить по предложениям", f"Ждут Вашего решения: {len(pending)}.", "cpm:automation"))
    if not any(x.status == "open" for x in s.slots):
        actions.append(Action("Открыть свободное время", "Впереди нет свободных слотов для записи.", "cpm:bk-open"))
    return tuple(actions[:limit])


def next_action(actions: tuple[Action, ...]) -> Action:
    return actions[0] if actions else Action("Ничего срочного", "Записанные факты не требуют Вашего действия.", "")


def attention(s: Any) -> tuple[str, ...]:
    """Donor _attention, limited to what is knowable here."""
    items = []
    cur = {p.currency for p in getattr(s.admin, "payments", {}).values()}
    if len(cur) > 1:
        items.append("Выручка есть в нескольких валютах; суммы не объединяются.")
    items.append("Источники клиентов и расходы на рекламу здесь не учитываются.")
    return tuple(items)


def screen(s: Any) -> tuple[str, list[list[tuple[str, str]]]]:
    q = action_queue(s)
    head = next_action(q)
    lines = [f"🧭 Что делать сейчас\n\nГлавное: {head.title}\n{head.reason}"]
    if len(q) > 1:
        lines.append("\nДальше:\n" + "\n".join(f"• {a.title}" for a in q[1:]))
    lines.append("\n" + "\n".join(f"ℹ️ {x}" for x in attention(s)))
    rows = [[(a.title[:40], a.cmd)] for a in q if a.cmd]
    return "\n".join(lines), rows



# --- donor growth_cockpit economics helpers (pure; callers pass profile/ledger/authorization data) ---

ALLOWED_PERIODS = frozenset({7, 30})
SOURCE_LABELS = {
    "direct": "Прямой источник", "organic": "Органика", "referral": "Рекомендации",
    "promotion": "Продвижение", "unknown": "Источник не определён", "yandex_direct": "Яндекс Директ",
    "telegram": "Telegram", "vk": "ВКонтакте", "max": "MAX", "website": "Сайт",
    "partner": "Партнёры", "manual_import": "Импорт / вручную",
}
_LEDGER = "durable_outcome_ledger"
_SPEND_LIVE = frozenset({"authorized", "launching", "active"})


@dataclass(frozen=True, slots=True)
class Metric:
    key: str
    value: int
    source: str
    meaning: str


@dataclass(frozen=True, slots=True)
class Money:
    amount_minor: int
    currency: str
    source: str
    meaning: str


@dataclass(frozen=True, slots=True)
class SourceResult:
    source: str
    outcomes: int
    label: str


@dataclass(frozen=True, slots=True)
class EconomicAction:
    title: str
    reason: str
    action_key: str
    source: str
    source_id: str | None = None


_ZERO_DEC = frozenset("BIF CLP DJF GNF ISK JPY KMF KRW PYG RWF UGX VND VUV XAF XOF XPF".split())
_THREE_DEC = frozenset("BHD IQD JOD KWD LYD OMR TND".split())


def minor_unit_exponent(currency: str) -> int:
    """ISO-4217 minor-unit exponent (donor domain.money.settlement_currency_minor_unit_exponent)."""
    c = str(currency or "").strip().upper()
    if len(c) != 3 or not c.isalpha() or c in ("XTS", "XXX"):
        raise ValueError("currency must be a known ISO 4217 code")
    return 0 if c in _ZERO_DEC else 3 if c in _THREE_DEC else 4 if c in ("CLF", "UYW") else 2


def acquisition_source_label(source: object) -> str:
    return SOURCE_LABELS.get(str(getattr(source, "value", source) or "").strip(), "Источник клиентов")


def business_zone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(str(timezone_name))
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("business timezone is invalid") from exc


def _aware(now: datetime) -> datetime:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("growth cockpit now must be timezone-aware")
    return now


def _day_bounds(zone: ZoneInfo, first: date, last: date) -> tuple[datetime, datetime]:
    return (datetime.combine(first, time.min, tzinfo=zone).astimezone(UTC),
            datetime.combine(last + timedelta(days=1), time.min, tzinfo=zone).astimezone(UTC))


def window_for_days(*, zone: ZoneInfo, days: int, now: datetime) -> tuple[datetime, datetime]:
    if days not in ALLOWED_PERIODS:
        raise ValueError("growth cockpit period must be 7 or 30 days")
    end = _aware(now).astimezone(zone).date()
    return _day_bounds(zone, end - timedelta(days=days - 1), end)


def today_window(*, zone: ZoneInfo, now: datetime) -> tuple[datetime, datetime]:
    d = _aware(now).astimezone(zone).date()
    return _day_bounds(zone, d, d)


def metrics(e: Any) -> tuple[Metric, ...]:
    """Period metrics from a unit-economics snapshot (leads/qualified/bookings/paid)."""
    return (
        Metric("leads", int(e.leads), _LEDGER, "Новые обращения за выбранный период."),
        Metric("qualified_leads", int(e.qualified_leads), _LEDGER, "Обращения, по которым подтверждён интерес клиента."),
        Metric("bookings", int(e.bookings), _LEDGER, "Новые записи за выбранный период."),
        Metric("paid_customers", int(e.paid_customers), _LEDGER, "Клиенты с подтверждённой оплатой."),
    )


def revenue(e: Any) -> tuple[Money, ...]:
    return tuple(Money(int(i.amount_minor), str(i.currency), "revenue_attribution",
                       "Подтверждённая выручка по известным источникам.") for i in e.revenue_by_currency)


def what_worked(e: Any) -> tuple[SourceResult, ...]:
    rows = [SourceResult(str(getattr(s, "value", s)), int(n), acquisition_source_label(s))
            for s, n in dict(e.source_breakdown).items() if int(n) > 0]
    rows.sort(key=lambda r: (-r.outcomes, r.label, r.source))
    return tuple(rows)


def money_text(amount_minor: int, currency: str) -> str:
    """Display money with the settlement minor-unit exponent (no cross-currency sums)."""
    exp = minor_unit_exponent(currency)
    amount = Decimal(int(amount_minor)) / (Decimal(10) ** exp)
    rendered = f"{amount:,.{exp}f}" if exp else f"{amount:,.0f}"
    return f"{rendered.replace(',', ' ')} {str(currency).upper()}"


def utc(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("economic action timestamp must be timezone-aware")
    return parsed.astimezone(UTC)


def current_approved_spend(authorizations: list[Any], *, now: datetime) -> Any | None:
    """First consented, unexpired spend authorization (read-only; never launches spend)."""
    cur = now.astimezone(UTC)
    for a in authorizations:
        if str(getattr(a.status, "value", a.status)) not in _SPEND_LIVE or a.consent_receipt is None:
            continue
        try:
            if utc(a.authorization_expires_at) <= cur or utc(a.snapshot.valid_until) <= cur:
                continue
        except (TypeError, ValueError):
            continue
        return a
    return None


def economic_next_action(*, open_slots: int, reactivation: list[Any], authorizations: list[Any],
                         journey: Any, now: datetime) -> EconomicAction | None:
    """Capacity first, then free reactivation, then already-consented paid acquisition."""
    if open_slots < 1:
        return EconomicAction(
            "Сначала открыть время для записи",
            "Свободных времён нет. До привлечения или возврата клиентов сначала нужно создать доступное "
            "время — так ClientPlatform не предлагает тратить деньги на спрос, который сейчас нельзя принять.",
            "economic_open_slots", "booking_availability")
    routable = [r for r in reactivation if r.route_platform]
    if routable:
        rc = int(journey.reactivated_customers)
        history = f" За выбранный период уже подтверждено возвратов: {rc}." if rc > 0 else ""
        return EconomicAction(
            "Сначала вернуть существующих клиентов",
            f"Есть {len(routable)} клиент(ов) из reactivation cohort с доступным разрешённым каналом и "
            "свободное время для записи. Начните с этого без рекламных расходов; сообщение само не "
            "отправится." + history,
            "economic_reactivation", "retention_projection", routable[0].candidate.customer_id)
    approved = current_approved_spend(authorizations, now=now)
    if approved is None:
        return None
    paid = next((int(s.paid_customers) for s in journey.sources
                 if str(getattr(s.source, "value", s.source)) == "yandex_direct"), 0)
    history = (f" За выбранный период Яндекс Директ дал оплативших клиентов: {paid}." if paid > 0
               else " Исторические оплаты из Яндекс Директ за выбранный период не подтверждены.")
    return EconomicAction(
        "Проверить уже разрешённое платное привлечение",
        f"Свободных времён: {open_slots}. Владелец уже подтвердил рекламные пределы: "
        f"общий {money_text(approved.hard_cap_minor, approved.currency)}, "
        f"дневной {money_text(approved.daily_cap_minor, approved.currency)}. "
        "Любой расход остаётся только внутри этих consent-bound лимитов." + history,
        "economic_paid_acquisition", "ad_spend_authorization", approved.id)


__all__ = [
    "acquisition_source_label", "business_zone", "economic_next_action", "metrics", "money_text",
    "revenue", "today_window", "what_worked", "window_for_days","CANON_GROWTH_COCKPIT", "Action", "action_queue", "attention", "customer_work_actions", "next_action", "screen"]

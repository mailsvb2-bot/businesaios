"""Owner cockpit money screens (donor native_member_interactions payments / prices / growth report).

Pure: renders ``(text, rows)`` from business_admin / sales / bookings projections. The only
mutation is a full refund button, which goes through ``admin.refund_payment`` (one reducer,
idempotent by refund reference) exactly like ``/refund``.
"""

from __future__ import annotations

from typing import Any

from application.business_flows import admin as ad
from application.business_flows import sales as sl

CANON_COCKPIT_MONEY = True
PARENTS = {
    "payments": "cpm:money",
    "pay-refund": "cpm:payments:0",
    "prices": "cpm:services",
    "growth-report": "cpm:growth",
}
MUTATIONS = frozenset({"pay-rf"})
PAGE = 6


def _pay(st: Any, payment_id: str) -> ad.ManualPaymentRecord:
    pay = (getattr(st, "payments", None) or {}).get(payment_id)
    if pay is None:
        raise ValueError("unknown payment")
    return pay


def _label(p: ad.ManualPaymentRecord) -> str:
    """Donor _native_money_text: amount, offering, refund state; reference shown masked."""
    tail = ""
    if p.refunded_minor:
        tail = " · возвращено полностью" if p.remaining_minor <= 0 else f" · возврат {ad.money(p.refunded_minor, p.currency)}"
    return f"{ad.money(p.amount_minor, p.currency)} · {p.offering} · №…{p.reference[-4:]}{tail}"


def screen(action: str, args: tuple[str, ...], s: Any) -> tuple[str, list[list[tuple[str, str]]]]:
    adm = s.admin or ad.State()
    if action == "payments":
        items = list(adm.payments.values())[::-1]
        if not items:
            return "💳 Платежи\n\nЗаписанных платежей нет. Записать: /pay Услуга | 1500 RUB | номер", []
        page = int(args[0]) if args and args[0].isdigit() else 0
        pages = -(-len(items) // PAGE)
        if page >= pages:
            raise ValueError("page")
        chunk = items[page * PAGE : (page + 1) * PAGE]
        rows = [
            [(f"↩️ Возврат …{p.reference[-4:]}", f"cpm:pay-refund:{p.payment_id}")]
            for p in chunk
            if p.remaining_minor > 0
        ]
        nav = [("◀️", f"cpm:payments:{page - 1}")] if page else []
        nav += [("▶️", f"cpm:payments:{page + 1}")] if page + 1 < pages else []
        body = "\n".join(f"• {_label(p)}" for p in chunk)
        return f"💳 Платежи\n\n{body}\n\nСтраница {page + 1}/{pages}", [*rows, *([nav] if nav else [])]
    if action == "pay-refund":
        p = _pay(adm, args[0] if args else "")
        if p.remaining_minor <= 0:
            return f"Платёж {_label(p)} уже полностью возвращён.", []
        return (
            f"↩️ Вернуть {ad.money(p.remaining_minor, p.currency)} по платежу {_label(p)}?\n\n"
            "Здесь только запись о возврате: деньги переводите сами. Частичный возврат: /refund",
            [[("✅ Да, записать возврат", f"cpm:pay-rf:{p.payment_id}")]],
        )
    if action == "prices":
        body = "\n".join(f"• {k} — {ad.money(*v)}" for k, v in sorted(adm.prices.items())) or "Цен пока нет."
        return f"🧾 Цены\n\n{body}\n\nЗадать или изменить: /price Услуга | 1500 RUB", []
    if action == "growth-report":
        return growth_report(s), []
    raise ValueError(action)


def growth_report(s: Any) -> str:
    """Donor _growth_report_message, limited to facts this port records (no ad spend or attribution)."""
    leads = list(getattr(s.sales, "leads", {}).values()) if s.sales is not None else []
    won = sum(1 for x in leads if x.stage == sl.Stage.WON)
    lost = sum(1 for x in leads if x.stage == sl.Stage.LOST)
    booked = [x for x in s.all_slots if x.status == "booked"]
    past = [x for x in booked if x.starts_at_ms <= s.now_ms]
    att = getattr(s.series, "attendance", {}) or {}
    came = sum(1 for x in past if att.get((x.slot_id, x.customer_id)) == "attended")
    marked = sum(1 for x in past if (x.slot_id, x.customer_id) in att)
    lines = ["📈 Отчёт о росте", "", f"Обращения: {len(leads)} (купили {won}, отказ {lost}, в работе {len(leads) - won - lost})"]
    if won + lost:
        lines.append(f"Конверсия закрытых: {round(100 * won / (won + lost))}%")
    lines.append(f"Записи: {len(booked)} из {len(s.all_slots)} слотов")
    lines.append(
        f"Посещаемость: {came} из {marked} отмеченных" + (f" ({round(100 * came / marked)}%)" if marked else "")
        + (f", без отметки {len(past) - marked}" if len(past) > marked else "")
    )
    summary = ad.payment_summary(s.admin) if s.admin is not None else {}
    for cur, row in sorted(summary.items()):
        lines.append(f"Деньги {cur}: {row['count']} платежей, итого {ad.money(row['net_minor'], cur)}")
    if not summary:
        lines.append("Деньги: платежей не записано")
    lines.append(f"Партнёров: {len(s.partners)}")
    lines += ["", "Реклама и источники не учитываются: расходов и атрибуции в этой системе нет."]
    return "\n".join(lines)


def mutation(action: str, args: tuple[str, ...], s: Any) -> tuple[str, dict[str, Any] | None]:
    """``pay-rf:<payment_id>`` -> the same payment_refunded fact as ``/refund <ref>`` (full remainder)."""
    if action != "pay-rf" or len(args) != 1:
        raise ValueError("money mutation")
    p = _pay(s.admin, args[0])
    change = ad.refund_payment(s.admin, p.reference)
    text = f"✅ Возврат записан: {ad.money(change['amount_minor'], p.currency)}" if change else "Этот возврат уже записан."
    return text, change


__all__ = ["CANON_COCKPIT_MONEY", "MUTATIONS", "PARENTS", "growth_report", "mutation", "screen"]

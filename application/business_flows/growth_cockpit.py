"""Owner growth cockpit: one deterministic "what to do now" queue (port of ClientPlatform growth_cockpit).

Pure projection over existing facts (sales_pipeline, bookings, event_series, business_admin).
Owns no facts, makes no provider calls; every action points to an existing cockpit screen.
Ad spend and source attribution are not recorded in this port, so they are reported as absent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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


__all__ = ["CANON_GROWTH_COCKPIT", "Action", "action_queue", "attention", "customer_work_actions", "next_action", "screen"]

"""Owner cockpit sales screens (donor native_member_interactions sales workspace).

Pure: renders ``(text, rows)`` from the sales_pipeline projection and turns a stage
button into the same ``lead_event`` fact ``/lead`` produces (one reducer: sales.reduce).
"""

from __future__ import annotations

from typing import Any

from application.business_flows import sales as sl

CANON_COCKPIT_SALES = True
S = sl.Stage
CLOSED = (S.WON, S.LOST)
# donor stage buttons: contacted / qualified / checkout, then "paid" / "lost"
NEXT_EVENT = {
    S.DISCOVERED: "contact",
    S.ENGAGED: "need",
    S.NEED_KNOWN: "qualified",
    S.QUALIFIED: "offer",
    S.OFFER_PRESENTED: "checkout",
}
EVENT_LABELS = {
    "contact": "Связались",
    "need": "Потребность ясна",
    "qualified": "Интерес",
    "offer": "Предложение",
    "checkout": "Оформление",
    "paid": "✅ Оплатил",
    "declined": "❌ Не состоялось",
    "handoff": "🙋 Нужен человек",
    "resume": "▶️ Вернуть в работу",
}
PARENTS = {
    "sales": "cpm:work",
    "sales-lead": "cpm:sales",
    "sales-actions": "cpm:sales",
    "sales-recent": "cpm:sales",
    "sales-handoffs": "cpm:sales",
}
SCREENS = frozenset(PARENTS) | {"sales-ev"}


def _lead(st: Any, lead_id: str) -> sl.Lead:
    lead = (getattr(st, "leads", None) or {}).get(lead_id)
    if lead is None:
        raise ValueError("unknown lead")
    return lead


def _primary(lead: sl.Lead) -> tuple[str, str] | None:
    """Donor _sales_primary_button: one main next step for an open lead."""
    if lead.stage in CLOSED:
        return None
    if lead.handoff_open:
        return EVENT_LABELS["resume"], f"cpm:sales-ev:{lead.lead_id}:resume"
    ev = NEXT_EVENT.get(lead.stage, "paid")
    return EVENT_LABELS[ev], f"cpm:sales-ev:{lead.lead_id}:{ev}"


def screen(action: str, args: tuple[str, ...], st: Any, *, now_ms: int) -> tuple[str, list[list[tuple[str, str]]]]:
    leads = sl.ordered(st) if st is not None else []
    if action == "sales":
        open_leads = [x for x in leads if x.stage not in CLOSED][:6]
        rows: list[list[tuple[str, str]]] = []
        if any(x.handoff_open for x in leads):
            rows.append([("🙋 Нужно подключиться", "cpm:sales-handoffs")])
        lines = [f"• {x.name} · {sl.LABELS[x.stage]}" for x in open_leads] or ["Открытых обращений сейчас нет."]
        rows += [[(x.name[:32], f"cpm:sales-lead:{x.lead_id}")] for x in open_leads]
        due = len(sl.due_actions(st, now_ms=now_ms)) if st is not None else 0
        rows.append([("🗂 Недавно закрытые", "cpm:sales-recent")])
        tail = f"\n\nПросрочено шагов: {due} (/leads_due)" if due else ""
        return "💬 Обращения и продажи\n\n" + "\n".join(lines) + tail + "\n\nНовый лид: /lead_add Имя | источник", rows
    if action == "sales-lead":
        lead = _lead(st, args[0] if args else "")
        nxt = lead.next_action or "не задан (/lead_next)"
        text = (
            f"💬 {lead.name}\n\nСтадия: {sl.LABELS[lead.stage]}\nИсточник: {lead.source or 'не указан'}\n"
            f"Следующий шаг: {nxt}" + ("\nНужно Ваше личное участие" if lead.handoff_open else "")
        )
        rows = []
        main = _primary(lead)
        if main:
            rows.append([main])
        rows.append([("⋯ Ещё действия", f"cpm:sales-actions:{lead.lead_id}")])
        return text, rows
    if action == "sales-actions":
        lead = _lead(st, args[0] if args else "")
        if lead.stage in CLOSED:
            return f"💬 {lead.name}: обращение закрыто ({sl.LABELS[lead.stage]}). Вернуть: /lead_reopen", []
        evs = [NEXT_EVENT[lead.stage]] if lead.stage in NEXT_EVENT else []
        evs += ["paid", "declined", "resume" if lead.handoff_open else "handoff"]
        rows = [[(EVENT_LABELS[e], f"cpm:sales-ev:{lead.lead_id}:{e}")] for e in evs]
        return f"⋯ Действия: {lead.name}\n\nЗаметка: /lead_note · Следующий шаг: /lead_next", rows
    if action == "sales-recent":
        closed = [x for x in leads if x.stage in CLOSED][:7]
        lines = [f"• {x.name} · {sl.LABELS[x.stage]}" for x in closed] or ["Недавно закрытых обращений нет."]
        return "🗂 Недавно закрытые\n\n" + "\n".join(lines), [
            [(x.name[:32], f"cpm:sales-lead:{x.lead_id}")] for x in closed
        ]
    if action == "sales-handoffs":
        items = [x for x in leads if x.handoff_open][:4]
        lines = [f"{i}. {x.name} · ожидает" for i, x in enumerate(items, 1)] or [
            "Сейчас нет обращений, где требуется личное участие."
        ]
        rows = [[(f"✅ Готово {i}", f"cpm:sales-ev:{x.lead_id}:resume")] for i, x in enumerate(items, 1)]
        return "🙋 Нужно подключиться лично\n\n" + "\n".join(lines), rows
    raise ValueError(action)


def mutation(args: tuple[str, ...], st: Any) -> dict[str, Any]:
    """Donor _sales_mutation_message: a stage button -> the same lead_event fact as /lead."""
    if len(args) != 2 or args[1] not in sl.EVENTS:
        raise ValueError("sales mutation")
    lead = _lead(st, args[0])
    return {
        "step": "lead_event",
        "lead_id": lead.lead_id,
        "event": args[1],
        "stage": sl.reduce(lead.stage, args[1]).value,
    }


def result_text(change: dict[str, Any], st: Any) -> str:
    """Donor _sales_result_message."""
    return f"✅ {_lead(st, change['lead_id']).name}: {sl.LABELS[S(change['stage'])]}"


__all__ = ["CANON_COCKPIT_SALES", "PARENTS", "SCREENS", "mutation", "result_text", "screen"]

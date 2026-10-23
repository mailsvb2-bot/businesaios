"""Handlers for event-sourced business flows (application.business_flows).

Each handler replays the flow from the Event Store, applies one pure
transition and records it as the tracked event of the delivered reply, so a
transition exists iff the user-visible receipt exists.
"""

from __future__ import annotations

from typing import Any

from application.business_flows import bot_provisioning as botprov
from application.business_flows.projection import flow_payloads
from runtime.handler_impl.core.payloads import require_mapping, required_str
from runtime.handler_impl.domains.admin_ops import _card_outcome
from runtime.handlers.delivery_contract import delivery_kwargs


def send_tracked(
    body,
    effects,
    env,
    *,
    text: str,
    event_type: str | None,
    event_payload: dict[str, Any] | None,
    ok: bool = True,
    reason: str = "",
) -> dict[str, Any]:
    tenant_id, user_id = required_str(body, "tenant_id"), required_str(body, "user_id")
    tracked = dict(event_payload or {}) if event_type else None
    if tracked is not None:
        tracked.update(tenant_id=tenant_id, user_id=user_id)
    delivery = effects.send_message(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        tenant_id=tenant_id,
        user_id=user_id,
        text=text,
        reply_markup=None,
        track_event_type=event_type,
        track_payload=tracked,
        **delivery_kwargs(body),
    )
    return _card_outcome(delivery=delivery, ok=ok, reason=reason)


_BOT_STATUS_RU = {
    "awaiting_secret": "ожидает токен (передайте его через защищённую форму владельца)",
    "ready": "токен получен, ожидает проверки",
    "verifying": "идёт проверка бота",
    "completed": "подключён",
    "failed": "ошибка проверки — можно повторить",
    "cancelled": "отменён",
}


def handle_bot_provisioning(payload, effects, env, *, event_store):
    body = require_mapping(payload or {})
    tenant_id, user_id = required_str(body, "tenant_id"), required_str(body, "user_id")
    op, arg = str(body.get("op") or "status"), str(body.get("arg") or "")
    state = botprov.replay(flow_payloads(event_store, tenant_id=tenant_id, event_type="bot_provisioning@v1"))
    current = botprov.active(state)
    try:
        if op == "request":
            change = botprov.request(state, tenant_id=tenant_id, user_id=user_id, username=arg)
            text = (
                f"🤖 Заявка на подключение @{change['username']} создана.\nСтатус: {_BOT_STATUS_RU['awaiting_secret']}"
            )
        elif op == "cancel":
            if current is None:
                raise ValueError("bot_provisioning_not_found")
            change = botprov.transition(current, "cancel")
            text = f"🤖 Подключение @{current.username} отменено."
        else:
            change = None
            text = (
                "🤖 Активных подключений нет.\nСоздать: /connect_bot имя_бота"
                if current is None
                else f"🤖 @{current.username}: {_BOT_STATUS_RU[current.status.value]}"
            )
    except ValueError as exc:
        return send_tracked(
            body, effects, env, text=f"🤖 Не получилось: {exc}", event_type=None, event_payload=None, ok=True, reason=""
        )
    return send_tracked(
        body, effects, env, text=text, event_type="bot_provisioning@v1" if change else None, event_payload=change
    )


def _now_ms() -> int:
    import time

    return int(time.time() * 1000)


def handle_bookings(payload, effects, env, *, event_store, now_ms: int | None = None):
    """Slots/bookings with pull reminders: due 24h/1h reminders ride on the participant's next reply."""
    from application.business_flows import bookings as bk

    body = require_mapping(payload or {})
    tenant_id, user_id = required_str(body, "tenant_id"), required_str(body, "user_id")
    op, arg, now = str(body.get("op") or "list"), str(body.get("arg") or "").strip(), now_ms or _now_ms()
    facts = flow_payloads(event_store, tenant_id=tenant_id, event_type="bookings@v1")
    slots = bk.replay(facts)
    open_slots = bk.upcoming(slots, now_ms=now, status="open")
    mine = bk.upcoming(slots, now_ms=now, customer_id=user_id)
    pick = {"book": open_slots, "cancel": mine}.get(op, [])
    chosen = pick[int(arg) - 1] if arg.isdigit() and 0 < int(arg) <= len(pick) else None
    try:
        if op == "add_slot":
            change = bk.parse_slot(arg, now_ms=now)
            text = f"📅 Слот открыт: {bk.fmt(bk.replay([change])[change['slot_id']])}"
        elif op == "book":
            change = bk.book(slots, chosen, customer_id=user_id, now_ms=now)
            text = f"✅ Вы записаны: {bk.fmt(chosen)}\nНапомню {', '.join(l for _, l in bk.REMINDER_OFFSETS_MIN)} до начала."
        elif op == "cancel":
            change = bk.cancel(chosen, customer_id=user_id, now_ms=now)
            text = f"❎ Запись отменена: {bk.fmt(chosen)}"
        else:
            change = None
            rows = mine if op == "mine" else open_slots
            head = "🗓 Мои записи" if op == "mine" else "📅 Свободные слоты (записаться: /book N)"
            text = head + "\n\n" + ("\n".join(f"{i}. {bk.fmt(s)}" for i, s in enumerate(rows, 1)) or "Пока пусто.")
    except ValueError as exc:
        return send_tracked(body, effects, env, text=f"📅 Не получилось: {exc}", event_type=None, event_payload=None)
    due = [d for d in bk.due_reminders(slots, now_ms=now, sent=bk.sent_reminders(facts)) if d[0].customer_id == user_id]
    if due and change is None:
        slot, minutes, label = due[0]
        text = f"⏰ Напоминание ({label}): {bk.fmt(slot)}\n\n" + text
        change = {"step": "reminder_sent", "slot_id": slot.slot_id, "minutes": minutes}
    return send_tracked(
        body, effects, env, text=text, event_type="bookings@v1" if change else None, event_payload=change
    )


__all__ = ["handle_bookings", "handle_bot_provisioning", "send_tracked"]

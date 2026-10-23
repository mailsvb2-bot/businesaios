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
    to_user_id: str | None = None,
    reply_markup: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tenant_id = required_str(body, "tenant_id")
    user_id = to_user_id or required_str(body, "user_id")
    tracked = dict(event_payload or {}) if event_type else None
    if tracked is not None:
        tracked.update(tenant_id=tenant_id, user_id=user_id)
    delivery = effects.send_message(
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        tenant_id=tenant_id,
        user_id=user_id,
        text=text,
        reply_markup=reply_markup,
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
        elif op in {"attach", "verify"}:
            if current is None:
                raise ValueError("bot_provisioning_not_found")
            if op == "attach":
                change = botprov.transition(current, "secret_attached", credential_ref=arg.strip())
                text = f"🤖 Ссылка на токен для @{current.username} сохранена. Проверить: /verify_bot"
            else:
                change = _verify_bot(current, effects)
                ok_bot = change["status"] == "completed"
                text = (
                    f"🤖 @{current.username} подключён (getMe подтвердил бота)."
                    if ok_bot
                    else f"🤖 Проверка @{current.username} не прошла: {change.get('error_code')}. Повтор: /connect_bot"
                )
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


def _verify_bot(current, effects) -> dict[str, Any]:
    """getMe through the sealed Telegram effect; the token is resolved from its reference and never stored."""
    from runtime.platform.config.env_flags import env_str

    kind, _, name = current.credential_ref.partition(":")
    token = env_str(name, "").strip() if kind == "env" else ""
    if not token:
        return botprov.transition(current, "failed", error_code=f"credential_unresolved:{kind or 'none'}")
    try:
        report = effects.telegram_self_check(token=token)
    except Exception as exc:
        return botprov.transition(current, "failed", error_code=str(exc).split(":")[0][:60] or "getme_failed")
    return botprov.verify_identity(current, report)


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
    if op == "dispatch":
        return _dispatch_reminders(body, effects, env, bk, slots, facts, now)
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
        elif op == "home":
            change = None
            nxt = f"Ближайшая запись: {bk.fmt(mine[0])}" if mine else "Записей пока нет."
            text = (
                f"🏠 Личный кабинет\n\n{nxt}\nСвободных слотов: {len(open_slots)}\n\n"
                "/slots — расписание · /book N — записаться\n/my_bookings — мои записи · /cancel_booking N — отменить\n"
                "/export_data — мои данные · /delete_my_data — удалить данные"
            )
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


def _dispatch_reminders(body, effects, env, bk, slots, facts, now):
    """Push every due 24h/1h reminder to its participant; each delivery records its own idempotent fact."""
    due = bk.due_reminders(slots, now_ms=now, sent=bk.sent_reminders(facts))
    delivered = 0
    for slot, minutes, label in due:
        out = send_tracked(
            body,
            effects,
            env,
            text=f"⏰ Напоминание ({label}): {bk.fmt(slot)}\nОтменить: /my_bookings",
            event_type="bookings@v1",
            event_payload={"step": "reminder_sent", "slot_id": slot.slot_id, "minutes": minutes, "push": True},
            to_user_id=slot.customer_id,
        )
        delivered += bool((out or {}).get("ok", True))
    text = f"⏰ Напоминаний отправлено: {delivered} из {len(due)}."
    return send_tracked(body, effects, env, text=text, event_type=None, event_payload=None)


def handle_partners(payload, effects, env, *, event_store):
    """Owner partner search: add candidates, rank against goal terms (advisory, never contacts anyone)."""
    from application.business_flows import partners as pt

    body = require_mapping(payload or {})
    tenant_id = required_str(body, "tenant_id")
    op, arg = str(body.get("op") or "rank"), str(body.get("arg") or "").strip()
    known = pt.replay(flow_payloads(event_store, tenant_id=tenant_id, event_type="partners@v1"))
    try:
        if op == "add":
            change = pt.parse_partner(arg)
            text = f"🤝 Партнёр добавлен: {change['name']} (всего {len(known | {change['partner_id']: None})})"
            return send_tracked(body, effects, env, text=text, event_type="partners@v1", event_payload=change)
    except ValueError as exc:
        return send_tracked(body, effects, env, text=f"🤝 Не получилось: {exc}", event_type=None, event_payload=None)
    if op in {"status", "pitch", "ref"}:
        return _partner_card(body, effects, env, pt, known, op, arg, event_store)
    terms = [t for t in arg.replace(",", " ").split() if t]
    fits = pt.rank(known, terms)
    lines = [
        f"{i}. {f.partner.name} — {f.total:.0f}/100" + (f" ({'; '.join(f.reasons)})" if f.reasons else "")
        for i, f in enumerate(fits, 1)
    ]
    head = f"🤝 Партнёры под цель «{' '.join(terms) or 'любая'}» (рекомендации, ничего не отправляется):"
    return send_tracked(
        body,
        effects,
        env,
        text=head + "\n\n" + ("\n".join(lines) or "Список пуст: /partner_add"),
        event_type=None,
        event_payload=None,
    )


def _partner_card(body, effects, env, pt, known, op, arg, event_store):
    tenant_id = required_str(body, "tenant_id")
    facts = flow_payloads(event_store, tenant_id=tenant_id, event_type="partners@v1")
    ordered = sorted(known.values(), key=lambda p: p.name)
    head, _, rest = arg.partition(" ")
    partner = ordered[int(head) - 1] if head.isdigit() and 0 < int(head) <= len(ordered) else None
    change = None
    try:
        if partner is None:
            raise ValueError("partner_not_found: номер партнёра по алфавиту")
        if op == "status":
            change = pt.set_status(partner, pt.statuses(facts).get(partner.partner_id, "new"), rest.strip())
            text = f"🤝 {partner.name}: {pt.STATUSES[change['status']]}"
        elif op == "pitch":
            business, _, offer = rest.partition("|")
            pack = pt.pitch(partner, business=business.strip() or "наш проект", offer=offer.strip())
            text = f"✉️ {pack['subject']}\n\n{pack['outreach']}\n\n{pack['cta']}\n\nНапоминание: {pack['followup']}\n(Отправляете вы сами.)"
        else:
            text = f"🔗 Реферальный код партнёра {partner.name}: ref_{pt.referral_token(tenant_id, partner.partner_id)}"
    except ValueError as exc:
        return send_tracked(body, effects, env, text=f"🤝 Не получилось: {exc}", event_type=None, event_payload=None)
    return send_tracked(
        body, effects, env, text=text, event_type="partners@v1" if change else None, event_payload=change
    )


def handle_offer_ladder(payload, effects, env, *, event_store):
    """Owner offer ladder: add steps, show next eligible offers for an evidence score (no auto-selling)."""
    from application.business_flows import ladder as ld

    body = require_mapping(payload or {})
    tenant_id = required_str(body, "tenant_id")
    op, arg = str(body.get("op") or "show"), str(body.get("arg") or "").strip()
    steps, _ = ld.replay(flow_payloads(event_store, tenant_id=tenant_id, event_type="offer_ladder@v1"))
    try:
        if op == "add":
            change = ld.parse_step(arg, position=len(steps) + 1)
            text = f"🪜 Ступень {change['position']}: {ld.KINDS[change['kind']]} — {change['title']} (порог {change['min_score']:.2f})"
            return send_tracked(body, effects, env, text=text, event_type="offer_ladder@v1", event_payload=change)
        score = float(arg.replace(",", ".")) if arg else 1.0
        eligible = ld.candidates(steps, evidence_score=score)
    except ValueError as exc:
        return send_tracked(body, effects, env, text=f"🪜 Не получилось: {exc}", event_type=None, event_payload=None)
    lines = [
        f"{s.position}. {ld.KINDS[s.kind]} — {s.title}" + (" · нужно ваше подтверждение" if s.requires_approval else "")
        for s in eligible
    ]
    text = f"🪜 Доступные предложения при оценке {max(0.0, min(score, 1.0)):.2f}:\n\n" + (
        "\n".join(lines) or "Нет доступных ступеней."
    )
    return send_tracked(body, effects, env, text=text, event_type=None, event_payload=None)


def _cockpit(body, effects, env, future, steps, facts):
    """Owner cockpit screens (cpm:*) over the same projections; buttons re-enter this action."""
    from application.business_flows import bookings as bk
    from application.business_flows import cockpit as cp
    from application.business_flows import partners as pt

    snap = cp.Snapshot(
        slots=future,
        partners=list(pt.replay(facts("partners@v1")).values()),
        steps=steps,
        bots=list(botprov.replay(facts("bot_provisioning@v1")).values()),
        fmt_slot=bk.fmt,
    )
    text, rows = cp.render(cp.parse(str(body.get("arg") or "cpm:menu")), snap, is_owner=True)
    return send_tracked(body, effects, env, text=text, event_type=None, event_payload=None, reply_markup=cp.markup(rows))


def handle_business_ops_summary(payload, effects, env, *, event_store, now_ms: int | None = None):
    """Owner operations summary over the business-flow projections (read-only)."""
    from application.business_flows import bookings as bk
    from application.business_flows import ladder as ld
    from application.business_flows import partners as pt

    body = require_mapping(payload or {})
    tenant_id, now = required_str(body, "tenant_id"), now_ms or _now_ms()

    def facts(event_type: str) -> list[dict]:
        return flow_payloads(event_store, tenant_id=tenant_id, event_type=event_type)

    slots = bk.replay(facts("bookings@v1"))
    future = bk.upcoming(slots, now_ms=now)
    booked = [s for s in future if s.status == "booked"]
    steps, _ = ld.replay(facts("offer_ladder@v1"))
    if str(body.get("op") or "") == "cockpit":
        return _cockpit(body, effects, env, future, steps, facts)
    deletions = len(facts("privacy_deleted@v1"))
    bots = {p.get("username") for p in facts("bot_provisioning@v1") if p.get("username")}
    text = (
        "📊 Операционная сводка\n\n"
        f"Слоты впереди: {len(future)} (занято {len(booked)}, свободно {len(future) - len(booked)})\n"
        + (f"Ближайшая встреча: {bk.fmt(booked[0])}\n" if booked else "")
        + f"Партнёров в базе: {len(pt.replay(facts('partners@v1')))}\n"
        f"Ступеней лестницы предложений: {len(steps)}\n"
        f"Подключаемых ботов: {len(bots)}\n"
        f"Удалений ПДн по запросу: {deletions}"
    )
    return send_tracked(body, effects, env, text=text, event_type=None, event_payload=None)


__all__ = [
    "handle_bookings",
    "handle_business_ops_summary",
    "handle_bot_provisioning",
    "handle_offer_ladder",
    "handle_partners",
    "send_tracked",
]

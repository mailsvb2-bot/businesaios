"""Handlers for event-sourced business flows (application.business_flows).

Each handler replays the flow from the Event Store, applies one pure
transition and records it as the tracked event of the delivered reply, so a
transition exists iff the user-visible receipt exists.
"""

from __future__ import annotations

from dataclasses import replace
from functools import partial
from typing import Any

from application.business_flows import bot_provisioning as botprov
from application.business_flows.projection import flow_payloads, flow_rows
from runtime.handler_impl.core.payloads import require_mapping, required_str
from runtime.handler_impl.domains.admin_ops import _card_outcome
from runtime.handler_impl.domains.business_catalog_ops import (
    CATALOG_OPS,
    CHANNEL_OPS,
    EVENT_OPS,
    FOLLOWUP_OPS,
    PANEL_OPS,
    PROMO_OPS,
    XP_OPS,
    _ads,
    _catalog,
    _event_channels,
    _events,
    _external_products,
    _followups,
    _owner_journey,
    _panels,
    _promotions,
    _retention,
    _sales_inbound,
    _slot_with_offering,
    channel_reminder_copies,
)
from runtime.handler_impl.domains.public_event_ops import PUB_OPS, _landing, public_event_op
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
    # Answer the button callback once, on the first message of this handler run.
    cbq = body.pop("callback_query_id", None) if isinstance(body, dict) else None
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
        **({"callback_query_id": str(cbq)} if cbq else {}),
        **delivery_kwargs(body),
    )
    return _card_outcome(delivery=delivery, ok=ok, reason=reason)


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
    if op in PROMO_OPS:
        try:
            return _promotions(
                lambda t, ch: send_tracked(
                    body, effects, env, text=t, event_type="bookings@v1" if ch else None, event_payload=ch
                ),
                bk,
                op,
                arg,
                now,
                slots,
                facts,
                user_id=user_id,
                tenant_id=tenant_id,
                event_store=event_store,
            )
        except ValueError as exc:
            return send_tracked(
                body, effects, env, text=f"📣 Не получилось: {exc}", event_type=None, event_payload=None
            )
    if op in CHANNEL_OPS:
        try:
            return _event_channels(
                lambda t, ch: send_tracked(
                    body, effects, env, text=t, event_type="bookings@v1" if ch else None, event_payload=ch
                ),
                bk,
                op,
                arg,
                now,
                slots,
                facts,
                user_id=user_id,
                platform=str(body.get("platform") or "telegram"),
            )
        except ValueError as exc:
            return send_tracked(
                body, effects, env, text=f"🔗 Не получилось: {exc}", event_type=None, event_payload=None
            )
    if op in PANEL_OPS:  # read-only owner panels
        say = partial(send_tracked, body, effects, env, event_type=None, event_payload=None)
        return _panels(
            lambda t, _ch: say(text=t), bk, op, arg, now, slots, facts, tenant_id=tenant_id, event_store=event_store
        )
    if op in EVENT_OPS:
        try:
            return _events(
                lambda t, ch: send_tracked(
                    body, effects, env, text=t, event_type="bookings@v1" if ch else None, event_payload=ch
                ),
                lambda t, uid: send_tracked(
                    body, effects, env, text=t, event_type=None, event_payload=None, to_user_id=uid
                ),
                bk,
                op,
                arg,
                now,
                slots,
                tenant_id=tenant_id,
                event_store=event_store,
            )
        except ValueError as exc:
            return send_tracked(
                body, effects, env, text=f"📅 Не получилось: {exc}", event_type=None, event_payload=None
            )
    pick = {"book": open_slots, "cancel": mine}.get(op, [])
    chosen = pick[int(arg) - 1] if arg.isdigit() and 0 < int(arg) <= len(pick) else None
    try:
        if op == "add_slot":
            change = _slot_with_offering(bk, arg, now, tenant_id=tenant_id, event_store=event_store)
            text = f"📅 Слот открыт: {bk.fmt(bk.replay([change])[change['slot_id']])}"
        elif op == "book":
            change = bk.book(slots, chosen, customer_id=user_id, now_ms=now)
            text = f"✅ Вы записаны: {bk.fmt(chosen)}\nНапомню {', '.join(l for _, l in bk.REMINDER_OFFSETS_MIN)} до начала."
        elif op == "cancel":
            change = bk.cancel(chosen, customer_id=user_id, now_ms=now)
            text = f"❎ Запись отменена: {bk.fmt(chosen)}"
        elif op in ("home", "home_owner"):
            change = None
            nxt = f"Ближайшая запись: {bk.fmt(mine[0])}" if mine else "Записей пока нет."
            text = (
                f"🏠 Личный кабинет\n\n{nxt}\nСвободных слотов: {len(open_slots)}\n\n"
                "/slots — расписание · /book N — записаться\n/my_bookings — мои записи · /cancel_booking N — отменить\n"
                "/export_data — мои данные · /delete_my_data — удалить данные"
            )
            if op == "home_owner":
                text += _owner_journey(bk, slots, tenant_id=tenant_id, event_store=event_store)
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
        change = {"step": "reminder_sent", "slot_id": slot.slot_id, "minutes": minutes, "revision": slot.revision}
    return send_tracked(
        body, effects, env, text=text, event_type="bookings@v1" if change else None, event_payload=change
    )


def _dispatch_reminders(body, effects, env, bk, slots, facts, now):
    """Push every due 24h/3h/15m reminder to its participant; each delivery records its own idempotent fact."""
    due = bk.due_reminders(slots, now_ms=now, sent=bk.sent_reminders(facts))
    delivered = 0
    for slot, minutes, label in due:
        rtext = channel_reminder_copies(effects, env, body, facts, bk, slot, minutes, label)
        out = send_tracked(
            body,
            effects,
            env,
            text=rtext,
            event_type="bookings@v1",
            event_payload={
                "step": "reminder_sent",
                "slot_id": slot.slot_id,
                "minutes": minutes,
                "revision": slot.revision,
                "push": True,
            },
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


def _viewer_id(body) -> int:
    raw = str(body.get("user_id") or "")
    return int(raw) if raw.isdigit() and len(raw) <= 19 else 0


def _messenger_connections(admin_facts: list[dict]) -> list[dict]:
    """Native VK/MAX routes as messenger_switching connection rows (ids/usernames only, no token refs)."""
    from application.business_flows import native_channels as nc

    return [
        {
            "platform": r.platform,
            "status": r.status,
            "connection_type": "vk_community" if r.platform == "vk" else r.platform,
            "external_account_id": r.external_id if r.platform == "vk" else (r.username or r.external_id),
        }
        for r in nc.replay(admin_facts).values()
    ]


def _cockpit(body, effects, env, future, steps, facts, now, team=None, timed=None):
    """Owner cockpit screens (cpm:*) over the same projections; buttons re-enter this action."""
    from application.business_flows import admin as ad
    from application.business_flows import bookings as bk
    from application.business_flows import cockpit as cp
    from application.business_flows import cockpit_booking as cb
    from application.business_flows import cockpit_events as ce
    from application.business_flows import cockpit_money as cm
    from application.business_flows import cockpit_sales as cs
    from application.business_flows import event_series as es
    from application.business_flows import partners as pt
    from application.business_flows import sales as sl

    snap = cp.Snapshot(
        slots=future,
        partners=list(pt.replay(facts("partners@v1")).values()),
        steps=steps,
        bots=list(botprov.replay(facts("bot_provisioning@v1")).values()),
        fmt_slot=bk.fmt,
        admin=ad.replay(facts("business_admin@v1")),
        series=es.replay(facts("event_series@v1")),
        all_slots=sorted(bk.replay(facts("bookings@v1")).values(), key=lambda x: x.starts_at_ms),
        now_ms=now,
        money_text=ad.render_summary,
        sales=sl.replay(facts("sales_pipeline@v1")),
        sales_rows=timed("sales_pipeline@v1") if timed else [],
        team=team or {},
        viewer_id=_viewer_id(body),
        connections=_messenger_connections(facts("business_admin@v1")),
    )
    parsed = cp.parse(str(body.get("arg") or "cpm:menu"))
    if parsed.action == "sales-ev":
        try:
            change = cs.mutation(parsed.args, snap.sales)
        except ValueError as exc:
            return send_tracked(body, effects, env, text=f"⚠️ Не получилось: {exc}", event_type=None, event_payload=None)
        lead_screen = cp.Parsed("sales-lead", (change["lead_id"],))
        after = replace(snap, sales=sl.replay([*facts("sales_pipeline@v1"), change]))
        text, rows = cp.render(lead_screen, after, is_owner=True)
        return send_tracked(
            body,
            effects,
            env,
            text=cs.result_text(change, after.sales) + "\n\n" + text,
            event_type="sales_pipeline@v1",
            event_payload=change,
            reply_markup=cp.markup(rows),
        )
    if parsed.action in ce.MUTATIONS:
        try:
            note, change = ce.mutation(parsed.action, parsed.args, snap)
        except ValueError as exc:
            return send_tracked(body, effects, env, text=f"⚠️ Не получилось: {exc}", event_type=None, event_payload=None)
        after = replace(snap, series=es.replay([*facts("event_series@v1"), *([change] if change else [])]))
        text, rows = cp.render(cp.Parsed("ev-conduct"), after, is_owner=True)
        return send_tracked(
            body,
            effects,
            env,
            text=note + "\n\n" + text,
            event_type="event_series@v1" if change else None,
            event_payload=change or None,
            reply_markup=cp.markup(rows),
        )
    if parsed.action in cm.MUTATIONS:
        try:
            note, change = cm.mutation(parsed.action, parsed.args, snap)
        except ValueError as exc:
            return send_tracked(body, effects, env, text=f"⚠️ Не получилось: {exc}", event_type=None, event_payload=None)
        after = replace(snap, admin=ad.replay([*facts("business_admin@v1"), *([change] if change else [])]))
        text, rows = cp.render(cp.Parsed("payments", ("0",)), after, is_owner=True)
        return send_tracked(
            body,
            effects,
            env,
            text=note + "\n\n" + text,
            event_type="business_admin@v1" if change else None,
            event_payload=change,
            reply_markup=cp.markup(rows),
        )
    if parsed.action in cb.MUTATIONS:
        try:
            change = cb.mutation(parsed.args, snap.admin, now_ms=now)
        except ValueError as exc:
            return send_tracked(body, effects, env, text=f"⚠️ Не получилось: {exc}", event_type=None, event_payload=None)
        if change["slot_id"] in bk.replay(facts("bookings@v1")):
            return send_tracked(
                body, effects, env, text="Это время уже добавлено.", event_type=None, event_payload=None
            )
        text, rows = cp.render(cp.Parsed("bookings", ("0",)), snap, is_owner=True)
        return send_tracked(
            body,
            effects,
            env,
            text=cb.result_text(change) + "\n\nДобавить ещё: кнопка ниже.",
            event_type="bookings@v1",
            event_payload=change,
            reply_markup=cp.markup(rows),
        )
    text, rows = cp.render(parsed, snap, is_owner=True)
    return send_tracked(
        body, effects, env, text=text, event_type=None, event_payload=None, reply_markup=cp.markup(rows)
    )


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
        from core.admin import roles_read_model as rr

        team = {
            "roles": rr.team_roles_snapshot(event_store, tenant_id=tenant_id),
            "perms": rr.team_perms_snapshot(event_store, tenant_id=tenant_id),
        }
        return _cockpit(
            body,
            effects,
            env,
            future,
            steps,
            facts,
            now,
            team,
            timed=lambda et: flow_rows(event_store, tenant_id=tenant_id, event_type=et),
        )
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


def handle_business_admin(payload, effects, env, *, event_store, now_ms: int | None = None):
    """Owner admin ops (settings, autopilot, prices, recorded payments/refunds, approvals)."""
    from application.business_flows import admin as ad

    body = require_mapping(payload or {})
    tenant_id = required_str(body, "tenant_id")
    op, arg = str(body.get("op") or "summary"), str(body.get("arg") or "").strip()
    st = ad.replay(flow_payloads(event_store, tenant_id=tenant_id, event_type="business_admin@v1"))

    def done(text, change=None):
        return send_tracked(
            body, effects, env, text=text, event_type="business_admin@v1" if change else None, event_payload=change
        )

    if op in XP_OPS:
        try:
            facts_ = flow_payloads(event_store, tenant_id=tenant_id, event_type="business_admin@v1")
            return _external_products(done, op, arg, facts_, tenant_id=tenant_id, body=body, now_ms=now_ms or _now_ms())
        except ValueError as exc:
            return done(f"🔌 Не получилось: {exc}")
    try:
        if op == "setting":
            if "=" not in arg:
                return done("\n".join(f"{k} = {v}" for k, v in sorted(st.settings.items())) or "⚙️ Настроек пока нет.")
            ch = ad.set_setting(st, arg)
            return done(f"⚙️ {ch['key']} = {ch['value']}", ch)
        if op == "customer_archive":
            from application.business_flows import bookings as bk

            slots = bk.replay(flow_payloads(event_store, tenant_id=tenant_id, event_type="bookings@v1"))
            known = {x.customer_id for x in slots.values() if x.customer_id}
            ch = ad.archive_customer(st, arg, known)
            cid = arg.split()[0]
            if ch is None:
                return done(f"👤 Клиент {cid[-6:]}: без изменений.")
            hidden = ch["step"] == "customer_archived"
            return done(
                f"👤 Клиент {cid[-6:]} "
                + (
                    "скрыт из списка (история сохранена). Вернуть: /customer_archive ID off"
                    if hidden
                    else "возвращён в список."
                ),
                ch,
            )
        if op == "autopilot":
            ch = ad.set_autopilot(st, arg)
            on = ch["value"] == "1" if ch else st.autopilot
            return done(f"🤖 Автопилот {'включён' if on else 'выключен'}" + ("" if ch else " (без изменений)"), ch)
        if op == "price":
            if not arg:
                rows = [f"• {o} — {ad.money(a, c)}" for o, (a, c) in sorted(st.prices.items())]
                return done("🏷 Цены\n" + ("\n".join(rows) or "Цен пока нет."))
            ch = ad.set_price(st, arg)
            return done(f"🏷 {ch['offering']}: {ad.money(ch['amount_minor'], ch['currency'])}", ch)
        if op == "pay":
            ch, prior = ad.record_payment(st, arg)
            if ch is None:
                return done(f"💳 Платёж {prior.reference} уже записан ({ad.money(prior.amount_minor, prior.currency)})")
            text = f"💳 Платёж {ch['reference']}: {ad.money(ch['amount_minor'], ch['currency'])} — {ch['offering']}"
            return done(text, ch)
        if op == "refund":
            ch = ad.refund_payment(st, arg)
            return done(
                f"↩️ Возврат {ad.money(ch['amount_minor'], st.payments[ch['payment_id']].currency)} записан"
                if ch
                else "↩️ Этот возврат уже записан",
                ch,
            )
        if op in ad.APPROVAL_NEXT:
            ch = ad.decide_approval(st, op, arg)
            return done(f"✅ Решение записано: {ch['status']}", ch)
        if op in {"invites", "invite_new", "join"}:
            from application.business_flows import invites as iv

            facts_ = flow_payloads(event_store, tenant_id=tenant_id, event_type="business_admin@v1")
            invs, now = iv.replay(facts_), now_ms or _now_ms()
            if op == "invite_new":
                import secrets

                token = secrets.token_urlsafe(12)
                return done(iv.issued_text(token), iv.issue(token, now_ms=now))
            if op == "join":
                ch = iv.claim(invs, arg, customer_user_id=required_str(body, "user_id"), now_ms=now)
                return done("✅ Вы подключены к бизнесу. /slots — расписание, /me — кабинет", ch)
            customers = len({i.claimed_by for i in invs.values() if i.claimed_by})
            return done(iv.invites_text(invs, now_ms=now, customers=customers))
        if op.startswith("policy"):
            from application.business_flows import automation_policy as apol

            facts_ = flow_payloads(event_store, tenant_id=tenant_id, event_type="business_admin@v1")
            pols, now = apol.replay(facts_), now_ms or _now_ms()
            if op == "policy_draft":
                ch = apol.draft(pols, arg, now_ms=now)
                return done(f"📝 Черновик политики v{ch['version']}. Подтвердить: /policy_approve", ch)
            if op == "policy_approve":
                ch = apol.approve(pols, now_ms=now)
                return done(f"✅ Политика v{ch['version']} действует", ch)
            if op == "policy_revoke":
                ch = apol.revoke(pols, now_ms=now)
                return done(f"⛔ Политика v{ch['version']} отозвана — автоматизация остановлена", ch)
            if op == "policy_check":
                parts = [x.strip() for x in arg.split("|")]
                amount = ad.parse_money(parts[2])[0] if len(parts) > 2 and parts[2] else 0
                channel = parts[1] if len(parts) > 1 else ""
                from application.business_flows import catalog as cg

                tz = cg.replay(flow_payloads(event_store, tenant_id=tenant_id, event_type="business_admin@v1")).timezone
                verdict, why = apol.check(
                    pols, parts[0], channel=channel, amount_minor=amount, now_ms=now, timezone_name=tz
                )
                label = {"allow": "✅ Разрешено", "needs_approval": "🧾 Нужно подтверждение", "deny": "⛔ Запрещено"}[
                    verdict
                ]
                ch = None
                if verdict == "needs_approval":
                    eff = apol.effective(pols, now_ms=now)
                    ch = apol.approval_for(parts[0], channel, amount, version=eff.version, now_ms=now)
                    ch = None if ch["approval_id"] in st.approvals else ch
                return done(f"{label}: " + "; ".join(why) + ("\n/approvals" if verdict == "needs_approval" else ""), ch)
            return done(apol.render(pols, now_ms=now))
        if op in CATALOG_OPS:
            return _catalog(
                done, op, arg, flow_payloads(event_store, tenant_id=tenant_id, event_type="business_admin@v1")
            )
        if op.startswith("ad_"):
            from application.business_flows import sales as sl

            return _ads(
                body,
                done,
                st,
                op,
                arg,
                flow_payloads(event_store, tenant_id=tenant_id, event_type="business_admin@v1"),
                lambda: sl.replay(flow_payloads(event_store, tenant_id=tenant_id, event_type="sales_pipeline@v1")),
            )
        if op == "audit":
            facts_ = flow_payloads(event_store, tenant_id=tenant_id, event_type="business_admin@v1")
            return done(
                "🧾 Журнал действий владельца\n"
                + "\n".join(ad.audit_lines(facts_, limit=int(arg) if arg.isdigit() else 20))
            )
        if op.startswith("post"):
            from application.business_flows import publications as pb

            pubs, now = (
                pb.replay(flow_payloads(event_store, tenant_id=tenant_id, event_type="business_admin@v1")),
                now_ms or _now_ms(),
            )
            if op == "posts":
                due = pb.due(pubs, now_ms=now)
                return done(
                    "🗓 Календарь публикаций\n"
                    + "\n".join(pb.calendar_lines(pubs))
                    + (f"\n⏰ Пора опубликовать: {len(due)}" if due else "")
                )
            if op == "post_add":
                ch = pb.draft(pubs, arg, now_ms=now)
                return done("📝 Черновик сохранён" if ch else "📝 Такой черновик уже есть", ch)
            if op == "post_schedule":
                ch = pb.schedule(pubs, arg, now_ms=now)
                return done(
                    "🗓 Запланировано на " + pb.fmt_ts(ch["at_ms"]) + " МСК (опубликуете вы сами — напомню в /posts)", ch
                )
            ch = pb.transition(pubs, op.removeprefix("post_"), arg, now_ms=now)
            return done(
                {
                    "post_unschedule": "↩️ Снято с расписания",
                    "post_publish": "✅ Отмечено как опубликованное",
                    "post_retire": "🗄 В архиве",
                }[op]
                if ch
                else "🗄 Уже в архиве",
                ch,
            )
        if op == "approvals":
            rows = [ad.format_approval(i, a) for i, a in enumerate(st.approvals.values(), 1)]
            return done("🧾 Действия автоматизации на подтверждение\n" + ("\n".join(rows) or "Нет запросов."))
    except ValueError as exc:
        return done(f"⚠️ Не получилось: {exc}")
    return done(ad.render_summary(st))


def _markup(rows):
    from application.business_flows import cockpit as cp

    return cp.markup(rows)


def _visual(body, effects, env, facts, arg, done):
    """/visual Название [| стиль [| формат]] or /visual Название | style x: YandexART via executor."""
    from application.business_flows import event_landing as el
    from application.business_flows import visual_creatives as vc
    from runtime.platform.config.env_flags import env_str

    title, cmd, val = vc.parse_command(arg)
    st = vc.replay(facts("event_series@v1"))
    key = vc.key_for(title)
    if cmd == "style":
        return done(f"🎨 Стиль «{vc.STYLE_LABELS.get(val, val)}» запомнен.", vc.save_style(title, val))
    style = cmd if cmd in vc.STYLES else st.styles.get(key, "photo")
    fmt = cmd if cmd in vc.FORMATS else (val or "post")
    ld = el.replay(facts("event_series@v1")).get(el.key_for(title))
    brief = vc.build_brief(title, context=(ld.sections.get("about", "") if ld else ""), style=style, fmt=fmt)
    if brief.payload_key in st.generated:
        g = st.generated[brief.payload_key]
        return done(f"🖼 Такое изображение уже создано: {g['path']} ({g['size']} байт). Повтор не тратит бюджет.")
    folder = env_str("YANDEX_ART_FOLDER_ID", env_str("YANDEXGPT_FOLDER_ID", env_str("YANDEX_FOLDER_ID", ""))).strip()
    gen = getattr(effects, "marketing_image_generate", None)
    if not folder or gen is None:
        return done("🔒 Изображения доступны только через YandexART (нужен YANDEX_ART_FOLDER_ID и ключ).")
    dec = env.decision
    out = gen(
        decision_id=str(dec.decision_id),
        correlation_id=str(dec.correlation_id),
        admin_id=str(body.get("user_id") or "owner"),
        brief=brief.to_mapping(),
        payload_key=brief.payload_key,
    )
    if not (isinstance(out, dict) and out.get("ok")):
        return done("⚠️ YandexART сейчас недоступен, попробуйте позже.")
    fact = vc.generated_fact(brief, path=str(out.get("path") or ""), size=int(out.get("size") or 0))
    label = f"{vc.STYLE_LABELS[brief.style]}, {brief.width_ratio}:{brief.height_ratio}"
    return done(f"🖼 Изображение готово ({label}): {fact['path']}", fact)


def handle_event_series(payload, effects, env, *, event_store, now_ms: int | None = None):
    """Warm-ups before booked events and opt-in sales follow-ups after them (event_series@v1)."""
    from application.business_flows import admin as ad
    from application.business_flows import bookings as bk
    from application.business_flows import event_series as es

    body = require_mapping(payload or {})
    tenant_id, user_id = required_str(body, "tenant_id"), required_str(body, "user_id")
    op, arg, now = str(body.get("op") or "preview"), str(body.get("arg") or "").strip(), now_ms or _now_ms()

    def facts(event_type: str) -> list[dict]:
        return flow_payloads(event_store, tenant_id=tenant_id, event_type=event_type)

    st, slots = es.replay(facts("event_series@v1")), bk.replay(facts("bookings@v1"))

    def done(text, change=None):
        return send_tracked(
            body, effects, env, text=text, event_type="event_series@v1" if change else None, event_payload=change
        )

    try:
        if op in PUB_OPS:
            return public_event_op(op, arg, body=body, effects=effects, env=env, facts=facts, done=done, now_ms=now)
        if op == "landing":
            return _landing(body, effects, env, facts, slots, arg, done)
        if op == "visual":
            return _visual(body, effects, env, facts, arg, done)
        if op in ("offers_on", "offers_off"):
            on = op == "offers_on"
            msg = (
                "🔔 Буду присылать предложения после встреч."
                if on
                else "🔕 Предложения больше не придут. Вернуть: /offers_on"
            )
            return done(msg, es.consent(user_id, on))
        if op == "warmup_days":
            ch = es.parse_warmup_days(arg)
            return done("🔥 Прогрев: за " + ", ".join(str(d) for d in ch["days"]) + " дн. до встречи", ch)
        if op == "text":
            ch = es.set_text(arg)
            return done(f"✏️ Текст {ch['kind']} {ch['segment']} {ch['stage']} сохранён", ch)
        if op == "reset":
            ch = es.reset_text(arg)
            return done(f"↩️ Текст {ch['kind']} {ch['segment']} {ch['stage']} — снова шаблон", ch)
        if op == "attendance":
            past = sorted(
                (s for s in slots.values() if s.status == "booked" and s.starts_at_ms <= now),
                key=lambda s: -s.starts_at_ms,
            )
            if not arg:
                rows = [
                    f"{i}. {bk.fmt(s)} — {st.attendance.get((s.slot_id, s.customer_id), 'не отмечено')}"
                    for i, s in enumerate(past[:10], 1)
                ]
                return done(
                    "🧾 Прошедшие встречи (/attendance N attended|no_show)\n" + ("\n".join(rows) or "Пока нет.")
                )
            n, _, status = arg.partition(" ")
            slot = past[int(n) - 1] if n.isdigit() and 0 < int(n) <= len(past) else None
            return done("🧾 Отмечено: " + status.strip(), es.mark_attendance(slot, status.strip(), now_ms=now))
        if op == "wizard_start":
            from application.business_flows import event_wizard as wz

            ch = wz.draft(user_id, arg)
            text, rows, _ = wz.step(ch["title"], "", now_ms=now)
            return send_tracked(
                body,
                effects,
                env,
                text=text,
                event_type="event_series@v1",
                event_payload=ch,
                reply_markup=_markup(rows),
            )
        if op == "wizard":
            from application.business_flows import event_wizard as wz

            title = wz.draft_title(facts("event_series@v1"), user_id)
            text, rows, result = wz.step(title, arg, now_ms=now)
            if result is None:
                return send_tracked(
                    body, effects, env, text=text, event_type=None, event_payload=None, reply_markup=_markup(rows)
                )
            slot = result["slot"]
            if result["warmup"]:
                send_tracked(
                    body,
                    effects,
                    env,
                    text="🔥 Прогрев: за " + ", ".join(map(str, result["warmup"]["days"])) + " дн.",
                    event_type="event_series@v1",
                    event_payload=result["warmup"],
                )
            send_tracked(
                body,
                effects,
                env,
                text="🧭 Мастер завершён",
                event_type="event_series@v1",
                event_payload={"step": "wizard_done", "user_id": user_id},
            )
            send_tracked(
                body,
                effects,
                env,
                text="📌 Формат: " + wz.MODES[result["mode"]["mode"]],
                event_type="event_series@v1",
                event_payload=result["mode"],
            )
            sent = None
            for slot in result["slots"]:
                sent = send_tracked(
                    body,
                    effects,
                    env,
                    text="✅ Слот открыт: "
                    + bk.fmt(bk.Slot(slot["slot_id"], slot["title"], slot["starts_at_ms"], slot["duration_min"]))
                    + f", {slot['duration_min']} мин",
                    event_type="bookings@v1",
                    event_payload=slot,
                )
            hint = "ссылку на комнату (https://…)" if result["mode"]["mode"] == "on" else "адрес площадки"
            send_tracked(
                body,
                effects,
                env,
                text=f"Дальше: /event_place {slot['title']} | {hint}",
                event_type=None,
                event_payload=None,
            )
            return sent
        if op == "followups":
            st = es.replay(facts("event_series@v1"))
            if not arg.strip():
                return done(es.followup_status(st), None)
            ch = es.followup_settings(st, arg)
            st2 = es.replay([*facts("event_series@v1"), ch])
            return done(es.followup_status(st2), ch)
        if op == "place":
            from application.business_flows import event_wizard as wz

            title, _, value = arg.partition("|")
            known = wz.places(facts("event_series@v1")).get(" ".join(title.split()).casefold()[:120], {})
            mode = known.get("mode") or ("on" if value.strip().startswith("https://") else "off")
            ch = wz.place_fact(title, value.strip(), mode=mode)
            return done(("💻 Комната: " if mode == "on" else "📍 Площадка: ") + ch["place"], ch)
        if op == "dispatch":
            offer = ad.replay(facts("business_admin@v1")).settings.get("offer_url", "")
            due = es.due_messages(st, slots, now_ms=now, offer_url=offer)
            sent = 0
            for m in due:
                out = send_tracked(
                    body,
                    effects,
                    env,
                    text=m["text"],
                    event_type="event_series@v1",
                    event_payload={"step": "series_sent", "key": m["key"], "kind": m["kind"]},
                    to_user_id=m["to"],
                )
                sent += bool((out or {}).get("ok", True))
            note = "" if offer else "\n(Продажные письма выключены: задайте /setting offer_url = https://…)"
            return done(f"📨 Серия: отправлено {sent} из {len(due)}." + note)
    except ValueError as exc:
        return done(f"⚠️ Не получилось: {exc}")
    return done("🗂 Сообщения серии\n\n" + "\n".join(es.previews(st)))


def handle_sales_pipeline(payload, effects, env, *, event_store, now_ms: int | None = None):
    """Owner sales pipeline (sales_pipeline@v1): leads, stages, next actions, notes, handoff."""
    from application.business_flows import sales as sl

    body = require_mapping(payload or {})
    tenant_id = required_str(body, "tenant_id")
    op, arg, now = str(body.get("op") or "list"), str(body.get("arg") or "").strip(), now_ms or _now_ms()
    st = sl.replay(flow_payloads(event_store, tenant_id=tenant_id, event_type="sales_pipeline@v1"))

    def done(text, change=None):
        return send_tracked(
            body, effects, env, text=text, event_type="sales_pipeline@v1" if change else None, event_payload=change
        )

    if op == "inbound":
        return _sales_inbound(done, body, env, tenant_id=tenant_id, event_store=event_store)
    if op in FOLLOWUP_OPS:

        def push(*, text, to_user_id, change):
            out = send_tracked(
                body,
                effects,
                env,
                text=text,
                event_type="sales_pipeline@v1",
                event_payload=change,
                to_user_id=to_user_id,
            )
            return (out or {}).get("ok", True)

        return _followups(done, push, st, op, arg, now, tenant_id=tenant_id, event_store=event_store)
    try:
        if op == "add":
            ch = sl.add_lead(arg)
            if ch["lead_id"] in st.leads:
                return done("ℹ️ Такой лид уже есть: /leads")
            return done(f"🎯 Лид добавлен: {ch['name']}", ch)
        if op == "event":
            ch = sl.apply_event(st, arg)
            return done(f"🎯 {st.leads[ch['lead_id']].name}: {sl.LABELS[sl.Stage(ch['stage'])]}", ch)
        if op in {"retention", "reactivate"}:
            return _retention(done, st, op, arg, now, tenant_id=tenant_id, event_store=event_store)
        if op == "reopen":
            ch = sl.reopen(st, arg)
            return done("🔄 Лид снова в работе", ch)
        if op == "next":
            ref, _, rest = arg.partition(" ")
            if rest.strip() == "-":  # donor clear_sales_next_action
                ch = sl.clear_next(st, ref)
                return done("⏰ Следующий шаг снят" if ch else "ℹ️ Следующего шага не было", ch)
            ch = sl.set_next(st, arg, now_ms=now)
            return done("⏰ Следующий шаг записан", ch)
        if op == "assign":
            from core.admin import roles_read_model as rr

            members = set(rr.team_roles_snapshot(event_store, tenant_id=tenant_id)) | {str(body.get("user_id") or "")}
            ch = sl.assign(st, arg, members=members - {""})
            if ch is None:
                return done("ℹ️ Без изменений")
            who = ch["assignee"]
            return done(f"👤 {st.leads[ch['lead_id']].name}: " + (f"ведёт {who}" if who else "ответственный снят"), ch)
        if op == "claim":
            ch = sl.claim_handoff(st, arg, user_id=str(body.get("user_id") or ""))
            name = sl.pick(st, arg.strip()).name
            return done(f"🙋 {name}: разговор у Вас" + ("" if ch else " (уже)"), ch)
        if op == "handoffs":
            work = sl.handoff_work(st)
            rows = [f"• {x.name}" + (f" — ведёт {x.assignee}" if x.assignee else " — свободен") for x in work]
            return done(f"🙋 Ждут человека: {len(work)}\n\n" + ("\n".join(rows) or "Никого.") + "\n\nВзять: /lead_claim N")
        if op == "note":
            ch = sl.add_note(st, arg)
            return done("📝 Заметка сохранена", ch)
        if op == "ai":
            return _sales_ai(body, effects, env, st, arg, tenant_id=tenant_id, event_store=event_store)
        if op == "card":
            lead = sl.pick(st, arg)
            notes = "\n".join(f"• {n}" for n in lead.notes) or "Заметок нет."
            return done(
                f"👤 {lead.name} ({lead.source or 'источник не указан'})\nСтадия: {sl.LABELS[lead.stage]}\n{notes}"
            )
        if op == "due":
            due = sl.due_actions(st, now_ms=now)
            return done(
                "⏰ Пора сделать\n\n"
                + ("\n".join(f"• {x.name}: {x.next_action}" for x in due) or "Ничего не просрочено.")
            )
    except ValueError as exc:
        return done(f"⚠️ Не получилось: {exc}")
    return done(sl.render(st, now_ms=now))


def _sales_ai(body, effects, env, st, arg, *, tenant_id, event_store):
    """/lead_ai N | текст клиента -> draft reply note + optional stage button (never sent to the customer)."""
    from application.business_flows import admin as ad
    from application.business_flows import cockpit as cp
    from application.business_flows import cockpit_sales as cs
    from application.business_flows import sales as sl
    from application.business_flows import sales_ai as sa
    from runtime.platform.config.env_flags import env_str

    ref, _, text = (x.strip() for x in arg.partition("|"))
    lead = sl.pick(st, ref)
    settings = ad.replay(flow_payloads(event_store, tenant_id=tenant_id, event_type="business_admin@v1")).settings
    provider = env_str("MARKETING_LLM_PROVIDER", env_str("LLM_PROVIDER", "")).strip().casefold()
    try:
        mode = sa.egress_permit(settings, provider)
    except PermissionError as exc:
        return send_tracked(body, effects, env, text=f"🔒 {exc}", event_type=None, event_payload=None)
    clean, redacted = sa.prepare_text(text, mode=mode)
    system, user = sa.prompt(lead, clean)
    dec = env.decision
    out = effects.marketing_llm_complete(
        decision_id=str(dec.decision_id),
        correlation_id=str(dec.correlation_id),
        admin_id=str(body.get("user_id") or "owner"),
        system=system,
        user=user,
    )
    if not (isinstance(out, dict) and out.get("ok")):
        return send_tracked(
            body, effects, env, text="⚠️ ИИ сейчас недоступен, попробуйте позже.", event_type=None, event_payload=None
        )
    analysis = sa.parse_analysis(str(out.get("text") or ""))
    note, event = sa.suggestion(lead, analysis)
    rows = [[(cs.EVENT_LABELS[event], f"cpm:sales-ev:{lead.lead_id}:{event}")]] if event else []
    rows.append([("💬 Карточка лида", f"cpm:sales-lead:{lead.lead_id}")])
    from application.business_flows import ladder as ld

    steps, _ = ld.replay(flow_payloads(event_store, tenant_id=tenant_id, event_type="offer_ladder@v1"))
    offer = sa.verified_offer(steps, analysis)
    flag = (f"\n\n🪜 Подходящий шаг лестницы: {offer['title']}" if offer else "") + (
        "\n(контакты скрыты перед отправкой в ИИ)" if redacted else ""
    )
    return send_tracked(
        body,
        effects,
        env,
        text=f"🤖 {lead.name}: черновик ответа (не отправлен клиенту)\n\n{analysis['reply']}{flag}",
        event_type="sales_pipeline@v1",
        event_payload=note,
        reply_markup=cp.markup(rows),
    )


__all__ = [
    "handle_bookings",
    "handle_sales_pipeline",
    "handle_event_series",
    "handle_business_admin",
    "handle_business_ops_summary",
    "handle_offer_ladder",
    "handle_partners",
    "send_tracked",
]

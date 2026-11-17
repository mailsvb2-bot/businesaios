"""Business admin sub-dispatch split out of business_flow_ops (catalog, ads, retention)."""

from __future__ import annotations

from application.business_flows import ad_media as _ad_media
from application.business_flows import admin as ad
from application.business_flows import catalog as cg
from application.business_flows import event_channels as ec
from application.business_flows import event_notifications as en
from application.business_flows import owner_panels as op_
from application.business_flows import promotions as pm
from application.business_flows import sales as sl
from application.business_flows.projection import flow_payloads, flow_rows
from application.organization.registry import OrganizationRegistry
from contracts.organization import OrganizationStatus
from runtime.messaging_policy_alert_subscriptions.settings_key import SETTING_KEY
from runtime.messaging_policy_alert_subscriptions.settings_value_builder import canonical_alert_subscriptions_value
from runtime.platform.config.env_flags import env_str

CATALOG_OPS = frozenset(
    {
        "directions",
        "direction",
        "direction_add",
        "direction_edit",
        "direction_goal",
        "direction_archive",
        "direction_restore",
        "offerings",
        "offering_add",
        "offering_retire",
        "offering_restore",
        "offering_direction",
        "formats",
        "format_on",
        "format_off",
        "profile",
        "profile_set",
        "profile_details",
        "profile_confirm",
        "offering_process",
        "offering_process_purge",
    }
)
COMMERCE_OPS = frozenset({"commerce", "commerce_check", "commerce_expand"})


def _catalog(done, op, arg, facts_, now=None):
    """Directions / offerings / formats; archive keeps history (catalog.py)."""

    c = cg.replay(facts_)
    if op == "offering_process":
        return done(cg.process_text(cg.offering_process(c, arg)))
    if op == "offering_process_purge":  # retention batch: one tracked fact per purged process, owner-triggered
        due = cg.process_purge_due(c, now_ms=int(now), limit=int(arg) if arg.isdigit() else 100)
        for fact in due[:-1]:
            done(f"🧹 Процесс очищен: {c.offerings[fact['offering_id']].title}", fact)
        if not due:
            return done("🧹 Нечего очищать: нет замороженных процессов старше срока хранения.")
        last = due[-1]
        return done(f"🧹 Процесс очищен: {c.offerings[last['offering_id']].title}. Всего: {len(due)}", last)
    if op == "directions":
        return done(cg.directions_text(c, archived=arg.strip().casefold() == "archived"))
    if op == "direction":
        return done(cg.direction_text(c, arg))
    if op == "offering_direction":
        ch = cg.bind_offering(c, arg)
        return done("🔗 Направление предложения обновлено. /offerings" if ch else "Уже так.", ch)
    if op == "direction_add":
        ch = cg.create_direction(c, arg)
        return done("✅ Направление создано. /directions" if ch else "Такое направление уже есть.", ch)
    if op == "direction_edit":
        return done("✏️ Направление обновлено.", cg.edit_direction(c, arg))
    if op == "direction_goal":
        return done("🎯 Цель сохранена.", cg.set_goal(c, arg))
    if op in {"direction_archive", "direction_restore"}:
        restore = op == "direction_restore"
        msg = "♻️ Направление восстановлено." if restore else "📦 Направление в архиве, данные сохранены."
        return done(msg, cg.archive(c, arg, restore=restore))
    if op == "offering_add":
        ch = cg.create_offering(c, arg)
        return done("✅ Предложение добавлено. /offerings" if ch else "Такое предложение уже есть.", ch)
    if op == "offering_retire":
        return done("🗄 Убрано из активных; история сохранена.", cg.retire_offering(c, arg, now_ms=now))
    if op == "offering_restore":
        if not arg:
            rows = [f"{i}. {o.title}" for i, o in enumerate(cg.archived_offerings(c), 1)]
            return done("🗄 Архив предложений\n" + ("\n".join(rows) or "Пусто.") + "\nВернуть: /offering_restore N")
        return done("♻️ Предложение снова активно. /offerings", cg.restore_offering(c, arg))
    if op in {"format_on", "format_off"}:
        ch = cg.toggle_format(c, arg, enabled=op == "format_on")
        return done(("✅ Формат обновлён." if ch else "Уже так.") + "\n" + cg.formats_text(c), ch)
    if op == "formats":
        return done(cg.formats_text(c))
    if op == "profile_set":
        return done("✅ Профиль обновлён.", cg.save_profile(c, arg))
    if op == "profile":
        return done(cg.profile_text(c))
    if op == "profile_details":
        ch = cg.save_profile_details(c, arg)
        return done(cg.profile_review_text(cg.replay([*facts_, ch]) if ch else c), ch)
    if op == "profile_confirm":
        ch = cg.confirm_profile_details(c)
        return done("✅ Детали профиля подтверждены." if ch else "Уже подтверждено.", ch)
    return done(cg.offerings_text(c))


def _ads(body, done, st, op, arg, facts_, sl_replay=None):
    """Governed ad proposals: drafts, exact-cap consent via approvals, publish gated by connector truth."""
    from application.business_flows import ad_proposals as ap
    from interfaces.ads.registry import CONNECTORS

    drafts = ap.replay(facts_)
    if op == "ad_draft":
        ch = ap.draft(arg)
        return done(
            "📝 Черновик рекламы сохранён. Дальше: /ad_consent N | 5000 RUB", None if ch["draft_id"] in drafts else ch
        )
    if op == "ad_consent":
        floor = int(env_str("BUSINESAIOS_AD_MIN_WEEKLY_MINOR", "30000") or 30000)
        ch = ap.consent(drafts, arg, min_weekly_minor=floor)
        return done("🧾 Запрошено согласие владельца на кап. Решение: /approvals → /approve N", ch)
    if op == "ad_edit":
        ch = ap.edit_copy(drafts, arg)
        return done("✏️ Текст рекламы обновлён." if ch else "Без изменений.", ch)
    if op in {"ad_stats", "ad_report"}:
        from application.business_flows import ad_analytics as aa

        if op == "ad_stats":
            return done("📈 Статистика записана. /ad_report", aa.record(drafts, arg))
        leads = list(sl_replay().leads.values())
        return done(aa.report(drafts, aa.replay(facts_), leads))
    if op == "ad_creatives":  # advisory only: never changes provider budget/allocation
        return done(_creatives_text(arg))
    if op.startswith("ad_trial"):
        return done(*_trials(op, arg, facts_))
    if op == "ad_publish":
        truth = CONNECTORS["yandex_direct"]
        ready = bool(truth["production_ready"]) and bool(truth["requires_human_approval"])
        text, ch = ap.publish_decision(ap.by_ref(drafts, arg), st.approvals, production_ready=ready)
        return done(text, ch)
    return done(ap.list_text(drafts, st.approvals))


def _creatives_text(arg):
    """/ad_creatives [bookings|won] ; variant:job:bps:leads:bookings:won ; ... -> one bounded advisory step."""
    from application.business_flows import yandex_growth as yg

    parts = [p.strip() for p in arg.split(";") if p.strip()]
    metric = parts.pop(0) if parts and parts[0] in yg.CREATIVE_METRICS else "bookings"
    keys = ("variant_id", "publication_job_id", "allocation_bps", "leads", "bookings", "won")
    arms = []
    for p in parts:
        v = [x.strip() for x in p.split(":")]
        if len(v) != 6:
            raise ValueError("формат: вариант:job:bps:лиды:записи:продажи")
        arms.append({k: (x if i < 2 else int(x)) for i, (k, x) in enumerate(zip(keys, v, strict=True))})
    r = yg.creative_allocation(arms, running=True, metric=metric)
    rows = [f"🎯 Креативы ({metric}): {r['status']}"]
    if r.get("winner_variant_id"):
        rows.append(f"Лидер: {r['winner_variant_id']}")
    if r.get("evidence"):
        rows.append("Предложение (рекомендация, бюджет не меняется): " + ", ".join(
            f"{e['variant_id']} {e['current_allocation_bps'] / 100:.0f}%→{e['proposed_allocation_bps'] / 100:.0f}%"
            for e in r["evidence"]))
    return "\n".join(rows)


def _retention(done, st, op, arg, now, *, tenant_id, event_store):
    """/retention cohorts and /reactivate -> sales lead; never sends (retention.py)."""
    from application.business_flows import bookings as bk
    from application.business_flows import retention as rt

    settings = ad.replay(flow_payloads(event_store, tenant_id=tenant_id, event_type="business_admin@v1")).settings
    days = int(settings.get("retention_days", "45")) if settings.get("retention_days", "45").isdigit() else 45
    slots = bk.replay(flow_payloads(event_store, tenant_id=tenant_id, event_type="bookings@v1"))
    cands = rt.candidates(slots, now_ms=now, inactive_days=days)
    if op == "retention":
        return done(rt.text(cands, st, inactive_days=days))
    ch, cand = rt.prepare(st, cands, arg)
    return done(
        f"🎯 Лид на возврат: {cand.customer_id}. Следующий шаг: {cand.next_action}. Отправка — только через /followups"
        if ch
        else "ℹ️ Лид на этот цикл уже есть: /leads",
        ch,
    )


def _slot_with_offering(bk, arg, now, *, tenant_id, event_store):
    """/add_slot in the business timezone; ``#N`` binds the slot to catalog offering N."""

    c = cg.replay(flow_payloads(event_store, tenant_id=tenant_id, event_type="business_admin@v1"))
    change = bk.parse_slot(arg, now_ms=now, tz=c.timezone)
    title, offering_id = cg.resolve_slot_title(c, change["title"])
    if offering_id:
        change = {**change, "title": title, "offering_id": offering_id}
        change["slot_id"] = bk.stable_id("slot", change["starts_at_ms"], title)
    return change


def _sales_inbound(done, body, env, *, tenant_id, event_store):
    """Customer free text -> one lead_inbound fact (sales_intelligence); reply is the policy's text."""
    from application.business_flows import sales_inbound as si

    reply = str(body.get("reply") or "Спасибо, сообщение получено.")[:1000]
    settings = ad.replay(flow_payloads(event_store, tenant_id=tenant_id, event_type="business_admin@v1")).settings
    ai = settings.get("sales_ai", "off").strip().casefold() in ("on", "1", "true")
    try:
        fact = si.record_message(
            flow_payloads(event_store, tenant_id=tenant_id, event_type="sales_pipeline@v1"),
            channel="telegram",
            subject=str(body.get("user_id") or ""),
            name=str(body.get("name") or ""),
            source_ref="managed_bot",
            event_id=str(getattr(env.decision, "correlation_id", "") or getattr(env.decision, "decision_id", "")),
            text=body.get("arg"),
            ai_allowed=ai,
        )
    except ValueError:
        fact = None
    return done(reply, fact)


FOLLOWUP_OPS = frozenset({"followup", "followup_plan", "followup_cancel", "optout", "followup_dispatch"})


def _followups(done, push, st, op, arg, now, *, tenant_id, event_store):
    """Per-lead follow-ups (sales_followups.py); delivery only via ``push`` to the lead's Telegram id."""
    from application.business_flows import automation_policy as ap
    from application.business_flows import sales_followups as sf

    tz = cg.replay(flow_payloads(event_store, tenant_id=tenant_id, event_type="business_admin@v1")).timezone
    try:
        if op == "followup":
            lead = sl.pick(st, arg)
            return done(f"✉️ Напоминание клиенту {lead.name}\n\n{sf.status(lead)}")
        if op == "followup_plan":
            return done("✉️ Напоминание запланировано", sf.plan(st, arg, now_ms=now, tz=tz))
        if op == "followup_cancel":
            return done("✖️ Напоминание отменено", sf.cancel(st, arg))
        if op == "optout":
            return done("🚫 Клиенту больше не пишем по этому каналу", sf.optout(st, arg))
    except ValueError as exc:
        return done(f"⚠️ Не получилось: {exc}")
    if ap.in_quiet_hours(now, tz):
        return done("🌙 Сейчас тихие часы (22:00–08:00), отправка отложена.")
    due = sf.due(st, now_ms=now)
    sent = sum(
        bool(
            push(
                text=x.followup_text,
                to_user_id=x.customer_id,
                change={"step": "followup_sent", "lead_id": x.lead_id, "followup_id": x.followup_id},
            )
        )
        for x in due
    )
    return done(f"✉️ Напоминаний отправлено: {sent} из {len(due)}.")


PROMO_OPS = frozenset({"promote", "promotions", "promo_open", "promo_book"})


def _destination(camp, *, tenant_id, event_store):
    """Acquisition destination for a campaign over the replayed bot + native channel connections."""
    from application.business_flows import bot_provisioning as botprov
    from runtime.handler_impl.domains.business_flow_ops import _messenger_connections

    bots = list(botprov.replay(flow_payloads(event_store, tenant_id=tenant_id, event_type="bot_provisioning@v1")).values())
    conns = _messenger_connections(flow_payloads(event_store, tenant_id=tenant_id, event_type="business_admin@v1"))
    return pm.acquisition_destination(camp, base_url=env_str("PUBLIC_BASE_URL", ""), bots=bots, connections=conns)


def _promotions(done, bk, op, arg, now, slots, facts, *, user_id, tenant_id, event_store):
    """Slot promotions (donor ``promotions``): owner creates/refreshes, customer opens/books with attribution."""
    import secrets


    camps = pm.replay(facts)
    c = cg.replay(flow_payloads(event_store, tenant_id=tenant_id, event_type="business_admin@v1"))

    def line(slot_id: str) -> str:
        return bk.fmt(slots[slot_id], c.timezone) if slot_id in slots else "слот удалён"

    if op == "promotions":
        return done(pm.stats_text(camps, line), None)
    if op == "promote":
        n, _, channel = arg.partition(" ")
        opens = bk.upcoming(slots, now_ms=now, status="open")
        if not n.isdigit() and opens:  # donor prepare_nearest_acquisition_destination: no N -> nearest open slot
            n, channel = str(opens.index(pm.nearest_open_slot(opens)) + 1), arg.strip()
        if not n.isdigit() or not 0 < int(n) <= len(opens):
            raise ValueError("/promote [N] [канал] — N из /slots; без N — ближайшее свободное время")
        slot = opens[int(n) - 1]
        oid = next(
            (
                f.get("offering_id")
                for f in facts
                if f.get("step") == "slot_opened" and f.get("slot_id") == slot.slot_id
            ),
            None,
        )
        off = c.offerings.get(str(oid or ""))
        brief = pm.Brief(
            c.activity[:80],
            c.activity,
            off.title if off else slot.title,
            off.description if off else "",
            bk.fmt(slot, c.timezone),
            slot.duration_min,
        )
        ch = pm.save(
            camps, slot_id=slot.slot_id, channel=channel or "telegram", brief=brief, new_token=secrets.token_urlsafe(12)
        )
        camp = pm.replay([ch])[ch["promotion_id"]]
        links = pm.destination_lines(_destination(camp, tenant_id=tenant_id, event_store=event_store))
        return done(
            f"📣 Кампания [{camp.channel}] готова. Ссылка: /start {pm.PREFIX}{camp.token}\n"
            + "".join(x + "\n" for x in links)
            + "\n"
            + pm.card(camp, line(slot.slot_id)),
            ch,
        )
    token = pm.parse_start_payload(arg) or arg
    camp = pm.by_token(camps, token)
    slot = slots.get(camp.slot_id)
    if op == "promo_open":
        return done(pm.card(camp, line(camp.slot_id)), pm.opened_fact(camp, user_id))
    if slot is None or slot.status != "open" or slot.starts_at_ms <= now:
        raise ValueError("это время уже недоступно, смотрите /slots")
    ch = {
        **bk.book(slots, slot, customer_id=user_id, now_ms=now),
        "promotion_id": camp.campaign_id,
        "source_token": camp.token,
    }
    return done(f"✅ Вы записаны: {line(slot.slot_id)}", ch)


EVENT_OPS = frozenset({"add_sessions", "edit_slot", "event_schedule", "reschedule_slot", "schedule"})


def _events(done, push, bk, op, arg, now, slots, *, tenant_id, event_store):
    """Owner event editing over sessions (donor events + event_notifications reschedule)."""

    tz = cg.replay(flow_payloads(event_store, tenant_id=tenant_id, event_type="business_admin@v1")).timezone
    live = [s for s in bk.upcoming(slots, now_ms=now) if s.status != "closed"]
    if op == "schedule":
        rows = [
            f"{i}. {bk.fmt(s, tz)} · {'занят' if s.status == 'booked' else 'свободен'}" for i, s in enumerate(live, 1)
        ]
        tail = "\n\n/edit_slot N [мин] [название] · /reschedule_slot N ГГГГ-ММ-ДД ЧЧ:ММ · /event_schedule N — вся серия"
        return done("🗓 Расписание\n\n" + ("\n".join(rows) or "Пока пусто.") + tail, None)
    if op == "add_sessions":
        sessions = bk.parse_sessions(arg, now_ms=now, tz=tz)
        rows = "\n".join(bk.fmt(s, tz) for s in bk.replay(sessions).values())
        return done(f"📅 Сессии открыты ({len(sessions)}):\n{rows}", {"step": "sessions_opened", "sessions": sessions})
    n, _, rest = arg.partition(" ")
    if op == "event_schedule":  # "N\nline..." or "N line\nline..."
        n, rest = ([*arg.split(None, 1), ""])[:2]
    slot = live[int(n) - 1] if n.isdigit() and 0 < int(n) <= len(live) else None
    if op == "event_schedule":
        from application.business_flows import event_schedule_edit as ese

        if slot is None:
            raise ValueError("slot_not_found: /event_schedule N")
        series = op_.series_of(slot, slots)
        if not rest.strip():
            return done(ese.edit_message(series, tz=tz) + f"\n\nОтвет: /event_schedule {n} и строки ниже", None)
        text, ch, moved = ese.edit_result(series, rest, now_ms=now, tz=tz)
        for old, new in moved:
            if old.status == "booked" and old.customer_id:
                push(en.rescheduled_text(new, old.starts_at_ms, tz), old.customer_id)
        return done(text, ch)
    if op == "edit_slot":
        ch = bk.edit(slot, rest)
        new = bk.replay([{"step": "slot_opened", **slot.__dict__}, ch])[slot.slot_id]
        return done(f"✏️ Обновлено: {bk.fmt(new, tz)}", ch)
    ch = bk.reschedule(slot, rest, now_ms=now, tz=tz)
    moved = bk.replay([{"step": "slot_opened", **slot.__dict__}, ch])[slot.slot_id]
    moved = bk.Slot(
        **{**moved.__dict__, "revision": ch["revision"], "status": slot.status, "customer_id": slot.customer_id}
    )
    if slot.status == "booked" and slot.customer_id:
        push(en.rescheduled_text(moved, slot.starts_at_ms, tz), slot.customer_id)
    return done(f"🔁 Перенесено: {bk.fmt(moved, tz)}\nНапоминания пересчитаны (ревизия {ch['revision']}).", ch)


CHANNEL_OPS = frozenset({"link_channels", "channel_verify"})


def _event_channels(done, bk, op, arg, now, slots, facts, *, user_id, platform="telegram"):
    """Booking messenger verification (donor event_registration_channels)."""

    if op == "channel_verify":
        ch = ec.consume(
            facts, slots, token=ec.extract_token(arg) or "", platform=platform, external_subject=user_id, now_ms=now
        )
        slot = slots[ch["slot_id"]]
        extra = "\nСогласие на рекламные сообщения записано." if ch["marketing_consent"] else ""
        return done(
            f"✅ {platform}: аккаунт подтверждён для записи {bk.fmt(slot)}.\nНапоминания придут сюда.{extra}", ch
        )
    n, _, rest = arg.partition(" ")
    mine = bk.upcoming(slots, now_ms=now, customer_id=user_id)
    slot = mine[int(n) - 1] if n.isdigit() and 0 < int(n) <= len(mine) else None
    tokens, ch = ec.issue(slot, customer_id=user_id, marketing=rest.replace(",", " ").split(), now_ms=now)
    rows = "\n".join(f"{p}: /start {ec.PREFIX}{t}" for p, t in tokens.items())
    return done(f"🔗 Ссылки подтверждения (действуют 1 час, одноразовые):\n{rows}", ch)


PANEL_OPS = frozenset({"announce", "event_promo", "attention", "ad_channels", "ad_channel", "setup_channel", "journey"})


def _owner_journey(bk, slots, *, tenant_id, event_store):
    from application.business_flows import event_series as es

    def facts(t):
        return flow_payloads(event_store, tenant_id=tenant_id, event_type=t)

    leads = sl.replay(facts("sales_pipeline@v1")).leads.values()
    booked = {s.customer_id for s in slots.values() if s.customer_id}
    return op_.journey_text(
        leads=len(leads),
        slots=slots,
        attendance=es.replay(facts("event_series@v1")).attendance,
        payments=list(ad.replay(facts("business_admin@v1")).payments.values()),
        camps=pm.replay(facts("bookings@v1")),
        reactivated=sum(1 for x in leads if x.source.startswith("reactivation:") and x.customer_id in booked),
    )


def _panels(done, *a, **kw):
    """Owner read-only panels (owner_panels.py); never sends to customers, never spends."""
    try:
        return _panel(done, *a, **kw)
    except ValueError as exc:
        return done(f"📊 Не получилось: {exc}", None)


def _panel(done, bk, op, arg, now, slots, facts, *, tenant_id, event_store):
    from runtime.ads.connector_wiring import ad_connections_enabled, yandex_direct_configured

    ready = ad_connections_enabled() and yandex_direct_configured()
    if op == "ad_channels":
        return done(op_.ad_channels_text(yandex_ready=ready), None)
    if op == "ad_channel":
        return done(op_.ad_channel_text(op_.ad_channel(arg, yandex_ready=ready)), None)
    if op == "setup_channel":
        return done(op_.setup_text(arg), None)
    if op == "attention":
        due = bk.due_reminders(slots, now_ms=now, sent=bk.sent_reminders(facts))
        return done(op_.attention_text(*op_.attention(due, now_ms=now)), None)
    if op == "journey":
        return done(_owner_journey(bk, slots, tenant_id=tenant_id, event_store=event_store).lstrip(), None)
    live = [s for s in bk.upcoming(slots, now_ms=now) if s.status != "closed"]
    n, _, rest = arg.partition(" ")
    if not (n.isdigit() and 0 < int(n) <= len(live)):
        raise ValueError("укажите номер из /schedule")
    slot, camps = live[int(n) - 1], pm.replay(facts)
    if op == "announce":
        return done(op_.announcement(slot, slots, camps, description=rest), None)
    return done(op_.promotion_text(op_.promotion_snapshot(slot, slots, camps)), None)


XP_OPS = frozenset(
    {"xp_list", "xp_add", "xp_activate", "xp_bind", "xp_disable", "xp_feedback", "xp_value", "xp_ingest"}
)


def _external_products(done, op, arg, facts_, *, tenant_id, body, now_ms, vault=None):
    """External product connectors (external_products.py); facts carry secret refs only."""
    from datetime import UTC, datetime

    from application.business_flows import external_products as xp
    from runtime.integration.external_product_secrets import resolve_secret_ref

    st = xp.replay(facts_)
    parts = arg.split()

    def secret(cid):
        c = st.connectors.get(cid)
        return c and resolve_secret_ref(c.secret_ref, tenant_id=tenant_id, connector_id=cid, vault=vault)

    def need(n, usage):
        if len(parts) < n:
            raise ValueError(usage)
        return parts

    if op == "xp_list":
        rows = [f"• {c.connector_id} · {c.product_key} · {c.status} · {c.display_name}" for c in st.connectors.values()]
        return done(
            "🔌 Внешние продукты\n\n" + ("\n".join(rows) or "Коннекторов нет. /xp_add key env:SECRET_NAME Название")
        )
    if op == "xp_add":
        p = need(2, "/xp_add key env:NAME|vault:NAME [название]")
        ch = xp.provision(st, product_key=p[0], display_name=" ".join(p[2:]) or p[0], secret_ref=p[1])
        return done(
            f"🔌 Коннектор {ch['connector_id']} создан (ожидает активации: /xp_activate {ch['connector_id']})", ch
        )
    if op == "xp_activate":
        cid = need(1, "/xp_activate ID")[0]
        return done("✅ Коннектор активирован", xp.activate(st, cid, secret=secret(cid)))
    if op == "xp_bind":
        p = need(3, "/xp_bind ID customer_ref customer_id")
        return done("🔗 Привязано", xp.bind(st, p[0], customer_ref=p[1], customer_id=p[2]))
    if op == "xp_disable":
        return done("⛔ Коннектор отключён", xp.disable(st, need(1, "/xp_disable ID")[0]))
    if op == "xp_feedback":
        p = need(2, "/xp_feedback RECEIPT useful|incorrect|wrong_customer")
        return done("📝 Оценка записана", xp.record_feedback(st, p[0], p[1]))
    if op == "xp_value":
        snap = xp.value_snapshot(st, parts[0] if parts else None)
        return done("📈 Ценность сигналов\n" + "\n".join(f"{k}: {v}" for k, v in snap.items()))
    raw = str(body.get("raw_body") or "").encode("utf-8")
    h = {str(k).lower(): str(v) for k, v in dict(body.get("headers") or {}).items()}
    cid = str(body.get("connector_id") or "")
    try:
        fact, rid = xp.ingest_webhook(
            st,
            cid,
            secret=secret(cid),
            timestamp_header=h.get("x-businesaios-timestamp", ""),
            signature_header=h.get("x-businesaios-signature", ""),
            body=raw,
            now=datetime.fromtimestamp(now_ms / 1000, UTC),
        )
    except xp.SignatureError as exc:
        return done(f"rejected:{exc}")
    return done(f"accepted:{rid}" if fact else f"duplicate:{rid}", fact)


def channel_reminder_copies(effects, env, body, facts, bk, slot, minutes, label) -> str:
    """Mirror a due reminder to the participant's verified VK/MAX identities via the existing
    native provider queue; returns the reminder text (channel vk/max -> _NativeProviderQueueAdapter; MAX paced by ProviderPacingCoordinator)."""
    import hashlib


    text = f"⏰ Напоминание ({label}): {bk.fmt(slot)}\n" + en.reminder_text(slot, minutes)
    tenant_id = str(body.get("tenant_id") or "")
    business_id = str(body.get("business_id") or tenant_id)
    for (sid, cid, plat), subject in sorted(ec.channels(facts).items()):
        if sid != slot.slot_id or cid != slot.customer_id or plat not in ("vk", "max"):
            continue
        subject = subject.split(":", 1)[1] if subject.startswith(plat + ":") else subject
        native = {"provider_key": f"{plat}_messaging", "business_id": business_id}
        if plat == "vk":
            seed = f"{slot.slot_id}:{minutes}:{subject}".encode()
            native.update(peer_id=subject, random_id=int(hashlib.sha256(seed).hexdigest()[:8], 16))
        effects.send_message(
            decision_id=env.decision.decision_id, correlation_id=env.decision.correlation_id, tenant_id=tenant_id,
            business_id=business_id, user_id=subject, text=text, channel=plat,
            track_payload={"_provider_native": native},
        )  # fmt: skip
    return text


def _partner_growth(pt, op, arg, tenant_id, known, facts):
    """Partner campaigns (discovery provider not connected: preparation only) and confirmed referral results."""
    from datetime import UTC, datetime

    try:
        if op == "campaign":  # Название | N
            name, _, n = arg.partition("|")
            ch = pt.start_campaign(name, int(n.strip() or 50), today=datetime.now(UTC).date().isoformat())
            return (f"🤝 Кампания «{ch['name']}» (цель {ch['target_count']}) сохранена. Поиск партнёров "
                    "не подключён: добавляйте кандидатов /partner_add — никому ничего не отправляется."), ch
        tok, _, key = arg.partition(" ")  # ref_TOKEN ключ_результата
        ch = pt.record_referral_result(known, facts, tenant_id, tok, key)
        return ("✅ Результат партнёра учтён." if ch else "ℹ️ Этот результат уже учтён."), ch
    except (ValueError, LookupError) as exc:
        return f"🤝 Не получилось: {exc}", None


def _trials(op, arg, facts):
    """Creative A/B trials (donor /experiments): owner-entered metrics, CAS winner apply; never touches ads."""
    import time

    from application.business_flows import creative_trials as ct
    from application.business_flows import creative_winner as cw

    trials, now = ct.replay(facts), int(time.time() * 1000)
    try:
        if op == "ad_trial":
            ch = ct.record(arg, now_ms=now)
            return (f"🧪 Тест креативов {ch['trial_id'][:8]} сохранён. /ad_trial_view {ch['trial_id'][:8]}",
                    None if ch["trial_id"] in trials else ch)
        if op == "ad_trials":
            rows, more = ct.list_page(trials, role="owner", offset=int(arg) if arg.isdigit() else 0)
            lines = [f"• {t['trial_id'][:8]} {t['date_from']}…{t['date_to']} r{t['revision']}" for t in rows]
            return "🧪 Тесты креативов\n" + ("\n".join(lines) or "Пока нет: /ad_trial") + ("\n…ещё" if more else ""), None
        ref, _, fp = arg.partition(" ")
        trial = trials[ct.resolve_reference(trials, role="owner", reference=ref)]
        if op == "ad_trial_view":
            pv = cw.preview(trial)
            rec = pv["recommendation"]
            tail = f"\nПрименить: /ad_trial_apply {ref} {pv['fingerprint']}" if rec["status"] == "ready" else ""
            return f"🧪 {ref}: {rec['status']} {rec.get('winner_variant_id') or ''}".rstrip() + tail, None
        plan = cw.apply(trial, expected_revision=int(trial["revision"]), expected_fingerprint=fp.strip(), confirmed=True)
        return f"✅ Победитель {plan['winner_variant_id']} применён (ревизия {plan['revision']}).", ct.applied(plan, trial, now_ms=now)
    except (ValueError, PermissionError, cw.CreativeWinnerApplyError) as exc:
        return f"🧪 Не получилось: {exc}", None


def _revenue_text(op, arg, now, event_store, tenant_id):
    """Owner read-only attribution/outcome screens (promotions attribution spine; no spend input)."""

    adm = flow_rows(event_store, tenant_id=tenant_id, event_type="business_admin@v1")
    bkg = flow_rows(event_store, tenant_id=tenant_id, event_type="bookings@v1")
    win = {"occurred_from": now - 30 * 86_400_000, "occurred_to": now + 1}
    if op == "outcomes":
        rows = pm.outcomes(adm, bkg, outcome_type=arg if arg in ("payment", "refund", "booking") else "", limit=15)
        lines = [f"• {r['type']} {pm.money_minor(r['amount_minor'], r['currency']) if r['currency'] else ''}"
                 f" клиент {r['customer_id'] or '—'}" for r in rows]
        return "📒 Итоги (последние)\n\n" + ("\n".join(lines) or "Пока нет.")
    if op == "trace":
        if not arg:
            return "Формат: /attribution id_клиента"
        t = pm.customer_trace(bkg, arg)
        return (f"🧭 Первый контакт клиента {arg}: кампания {t['campaign_id']} [{t['channel']}] ({t['kind']})"
                if t else f"🧭 У клиента {arg} нет атрибутированного контакта.")
    if op == "economics":
        e = pm.unit_economics(adm, bkg, **win)
        ch = "\n".join(f"  {k}: {pm.money_minor(v, e['currency'])}" for k, v in e["revenue_by_channel_minor"].items())
        return (f"📈 Экономика за 30 дней\nЧистая выручка: {pm.money_minor(e['net_minor'], e['currency'])}\n"
                f"Платящих клиентов: {e['paying_customers']}\nПо каналам:\n{ch or '  —'}\n"
                "ROAS/CAC не считаются: расход не подтверждён рекламным кабинетом.")
    j = pm.revenue_journey(adm, bkg, **win)
    return (f"🛤 Путь клиента за 30 дней\nКонтакт: {j['touched']} → запись: {j['booked']} → оплата: {j['paid']}\n"
            f"Из контакта в оплату: {j['touched_then_paid']}")


def _visual(body, effects, env, facts, arg, done, *, now_ms: int = 0, event_store=None):
    """/visual Название [| стиль [| формат]] or /visual Название | style x: YandexART via executor."""
    from application.business_flows import event_landing as el
    from application.business_flows import visual_creatives as vc

    title, cmd, val = vc.parse_command(arg)
    st = vc.replay(facts("event_series@v1"))
    key = vc.key_for(title)
    if cmd == "style" and val == "clear":
        cleared, fs = vc.clear_style(title, st)
        return done("🎨 Стиль сброшен: снова «фото»." if cleared else "ℹ️ Свой стиль не был задан.", *fs[:1])
    if cmd == "style":
        return done(f"🎨 Стиль «{vc.STYLE_LABELS.get(val, val)}» запомнен.", vc.save_style(title, val))
    style = cmd if cmd in vc.STYLES else st.styles.get(key, "photo")
    fmt = cmd if cmd in vc.FORMATS else (val or "post")
    ld = el.replay(facts("event_series@v1")).get(el.key_for(title))
    brief = vc.build_brief(title, context=(ld.sections.get("about", "") if ld else ""), style=style, fmt=fmt)
    knobs = _ad_media.media_gen_operator_env(env_str)
    if _ad_media.media_gen_enabled(knobs):
        text, fact = _ad_media.generate_budgeted(
            facts=facts("event_series@v1"), brief=brief, env=knobs,
            now_ms=now_ms, event_store=event_store, tenant_id=str(body.get("tenant_id") or ""),
            call=lambda adapter: adapter(effects, env, body, brief),
        )
        return done(text, fact)
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


def _yandexart_media_adapter(effects, env, body, brief):
    folder = env_str("YANDEX_ART_FOLDER_ID", env_str("YANDEXGPT_FOLDER_ID",
                     env_str("YANDEX_FOLDER_ID", ""))).strip()
    generator = getattr(effects, "marketing_image_generate", None)
    if not folder or not callable(generator):
        return {"ok": False}
    return generator(
        decision_id=str(env.decision.decision_id),
        correlation_id=str(env.decision.correlation_id),
        admin_id=str(body.get("user_id") or ""),
        brief=brief.to_mapping(), payload_key=brief.payload_key,
    )


_ad_media.register_media_provider("yandexart", _yandexart_media_adapter)


def _visual_publish(body, facts, arg, done):
    """Separate explicit owner confirmation, never a side effect of generation."""
    from application.business_flows import event_series as es
    from application.business_flows import visual_creatives as vc

    if not _ad_media.media_gen_enabled(_ad_media.media_gen_operator_env(env_str)):
        return done("🔒 Публикация сгенерированных изображений выключена оператором.")
    try:
        key, event_id, stage, slot, confirmed = _ad_media.parse_media_publish(arg)
    except ValueError as exc:
        return done(str(exc))
    generated = vc.replay(facts("event_series@v1")).generated.get(key)
    if not generated:
        return done("Изображение с этим ключом не найдено. Создайте его через /visual.")
    if not confirmed:
        return done(f"Предпросмотр: {generated['path']} → {event_id} / {stage} / {slot}.\n"
                    f"Для подтверждения: /visual_publish {key} | {event_id} | {stage} | {slot} | да")
    state = es.replay(es.expand(facts("event_series@v1")))
    try:
        asset, events = es.store_generated_asset(
            state, event_id=event_id, stage=stage, slot_key=slot, kind="image",
            stored_reference=str(generated["path"]), source_ref=key,
        )
    except (ValueError, RuntimeError) as exc:
        return done(f"⚠️ Не удалось привязать изображение: {type(exc).__name__}")
    change = events[0] if len(events) == 1 else (
        {"step": "batch", "facts": events} if events else None
    )
    return done(f"✅ Изображение привязано к событию, ревизия {asset['revision']}.", change)


def _sales_ai(send, body, effects, st, arg, *, decision, tenant_id, event_store):
    """/lead_ai N | текст клиента -> draft reply note + optional stage button (never sent to the customer)."""
    from application.business_flows import cockpit as cp
    from application.business_flows import cockpit_sales as cs
    from application.business_flows import sales_ai as sa

    ref, _, text = (x.strip() for x in arg.partition("|"))
    lead = sl.pick(st, ref)
    settings = ad.replay(flow_payloads(event_store, tenant_id=tenant_id, event_type="business_admin@v1")).settings
    provider = env_str("MARKETING_LLM_PROVIDER", env_str("LLM_PROVIDER", "")).strip().casefold()
    try:
        mode = sa.egress_permit(settings, provider)
    except PermissionError as exc:
        return send(f"🔒 {exc}")
    clean, redacted = sa.prepare_text(text, mode=mode)
    system, user = sa.prompt(lead, clean)
    dec = decision
    out = effects.marketing_llm_complete(
        decision_id=str(dec.decision_id),
        correlation_id=str(dec.correlation_id),
        admin_id=str(body.get("user_id") or "owner"),
        system=system,
        user=user,
    )
    if not (isinstance(out, dict) and out.get("ok")):
        return send("⚠️ ИИ сейчас недоступен, попробуйте позже.")
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
    text = f"🤖 {lead.name}: черновик ответа (не отправлен клиенту)\n\n{analysis['reply']}{flag}"
    return send(text, note, cp.markup(rows))


def _commerce(done, body, st, op, arg, *, tenant_id, event_store):
    """Tariff usage/limits (ai_commerce port): usage from team roles + bookings customers; no private ledger."""

    usage = ad.commerce_usage(event_store, tenant_id, str(body.get("user_id") or ""), st.archived_customers)
    if op == "commerce_check":
        sku, _, units = arg.partition(" ")
        if not units.strip().isdigit():
            raise ValueError("формат: /commerce_check staff_seat|active_customer N")
        lim = ad.allowances(st)
        p = ad.commerce_proposal(
            operation_id=f"owner-check:{sku}:{units.strip()}", tenant_id=tenant_id, sku=sku.strip(),
            requested_units=int(units), used=usage.get(sku.strip(), 0), allowance=lim.get(sku.strip(), 0),
        )
        verdict = "нужен больший тариф" if p["kind"] == "upgrade" else "входит в тариф"
        return done(f"🧮 {ad.SKU_LABELS[p['sku']]} +{p['requested_units']}: {p['projected_total']}/{p['allowance']} — {verdict}")
    overview = ad.commerce_overview(st, tenant_id=tenant_id, usage=usage)
    if op == "commerce_expand":
        facts_ = flow_payloads(event_store, tenant_id=tenant_id, event_type="business_admin@v1")
        ch = ad.expansion_request(overview, tenant_id=tenant_id, known=ad.requested_cases(facts_))
        if ch is None:
            return done("📨 Запрос на расширение уже зарегистрирован; оператор свяжется в боте.")
        return done("📨 Запрос на расширение тарифа зарегистрирован (обращение billing).\n" + ch["title"], ch)
    return done(ad.commerce_text(overview))


def _organization_settings(*, event_store, idempotency_path, body, tenant_id, op, arg, decision_id):
    """Use the existing organization registry, not a second Telegram-owned store."""
    from pathlib import Path

    from reliability.idempotency_store import JsonlIdempotencyStore

    if not idempotency_path or not str(body.get("business_id") or "").strip():
        return "🏢 Выберите бизнес; реестр недоступен без подтверждённого контекста.", None
    try:
        registry = OrganizationRegistry(
            event_store=event_store,
            idempotency_store=JsonlIdempotencyStore(Path(idempotency_path)),
        )
        return organization_card(
            registry=registry, tenant_id=tenant_id,
            business_id=str(body["business_id"]),
            user_id=str(body["user_id"]), operation=op,
            arg=arg, decision_id=decision_id,
        )
    except (RuntimeError, ValueError, LookupError, OSError):
        return ("🏢 Не удалось открыть или сохранить карточку. Проверьте формат команды и доступ к реестру.",
                {"inline_keyboard": [[{"text": "⬅️ Настройки", "callback_data": "settings:menu"}]]})


def organization_card(*, registry: OrganizationRegistry, tenant_id: str, business_id: str,
                      user_id: str, operation: str, arg: str, decision_id: str) -> tuple[str, dict]:
    if operation not in {"organization_show", "organization_create", "organization_name", "organization_type"}:
        raise ValueError("unsupported_organization_operation")
    active = [
        item for item in registry.list_for_business(tenant_id=tenant_id, business_id=business_id)
        if item.status is OrganizationStatus.ACTIVE
    ]
    preferred = next((item for item in active if item.organization_id == business_id), None)
    if preferred is None:
        if len(active) > 1:
            raise ValueError("multiple_organizations_require_explicit_selection")
        preferred = active[0] if active else None
    if operation != "organization_show" and not arg:
        raise ValueError("organization_value_required")
    identity = {"tenant_id": tenant_id, "business_id": business_id}
    audit = {"actor_id": user_id, "decision_id": decision_id}
    if operation == "organization_create":
        if preferred is not None:
            raise ValueError("organization_already_exists")
        name, divider, kind = arg.partition("|")
        if not name.strip():
            raise ValueError("organization_name_required")
        preferred = registry.create(
            **identity, organization_id=business_id, idempotency_key=decision_id,
            name=name.strip(), organization_type=kind.strip() if divider else None,
            event_metadata=audit,
        )
    elif operation in {"organization_name", "organization_type"}:
        if preferred is None:
            raise ValueError("organization_not_created")
        field = "name" if operation == "organization_name" else "organization_type"
        if getattr(preferred, field) != arg.strip():
            preferred = registry.update(
                **identity, organization_id=preferred.organization_id,
                idempotency_key=decision_id, event_metadata=audit, **{field: arg.strip()},
            )
    if preferred is None:
        text = ("🏢 Организация\n\nКарточка ещё не создана.\n"
                "Создать: /org_create Название организации | тип")
    else:
        preferred = registry.get(**identity, organization_id=preferred.organization_id)
        text = (f"🏢 Организация\n\nНазвание: {preferred.name or 'не указано'}\n"
                f"Тип: {preferred.organization_type or 'не указан'}\n"
                f"Статус: {preferred.status.value}\n"
                f"ID: {preferred.organization_id}\n\n"
                "Изменить название: /org_name Новое название\n"
                "Изменить тип: /org_type Новый тип")
    return text, {"inline_keyboard": [
        [{"text": "🔄 Обновить карточку", "callback_data": "cp:settings:organization"}],
        [{"text": "⬅️ Настройки", "callback_data": "settings:menu"}],
    ]}


def notification_preferences(*, settings_gateway, tenant_id: str, user_id: str, operation: str) -> tuple[str, dict]:
    if operation not in {"notifications_show", "notifications_toggle", "notifications_level"}:
        raise ValueError("unsupported notification operation")
    if settings_gateway is None:
        raise RuntimeError("canonical_notification_settings_gateway_missing")
    levels = ("info", "warn", "critical")
    key = SETTING_KEY

    def own_entry(rows):
        return next((item for item in rows if item["recipient_user_id"] == user_id
                     and item["channel"] == "telegram" and not item["business_id"]), None)

    if operation != "notifications_show":
        for _ in range(3):
            before = settings_gateway.get_value(tenant_id=tenant_id, key=key)
            entries = canonical_alert_subscriptions_value(before, tenant_id=tenant_id)
            current = own_entry(entries) or {
                "recipient_user_id": user_id, "channel": "telegram", "business_id": "",
                "enabled": False, "min_level": "warn", "code_filters": [], "user_scope": [],
            }
            updated = dict(current)
            if operation == "notifications_toggle":
                updated["enabled"] = not bool(current["enabled"])
            else:
                updated["min_level"] = levels[(levels.index(current["min_level"]) + 1) % len(levels)]
            entries = [row for row in entries if not (row["recipient_user_id"] == user_id and row["channel"] == "telegram" and not row["business_id"])] + [updated]
            if settings_gateway.compare_and_set_value(
                tenant_id=tenant_id, key=key, expected=before, value=entries,
            ):
                break
        else:
            raise RuntimeError("notification_preferences_concurrent_change")
    after = canonical_alert_subscriptions_value(
        settings_gateway.get_value(tenant_id=tenant_id, key=key), tenant_id=tenant_id,
    )
    own = own_entry(after)
    enabled, level = bool(own and own["enabled"]), own["min_level"] if own else "warn"
    text = ("🔔 Системные уведомления\n\nПолучатель: ваш Telegram-аккаунт\n"
            f"Оповещения: {'включены' if enabled else 'выключены'}\n"
            f"Минимальная важность: {level}\n\n"
            "Настройки относятся к служебным оповещениям, а не к рекламным рассылкам.")
    return text, {"inline_keyboard": [
        [{"text": "🔕 Отключить" if enabled else "🔔 Включить",
          "callback_data": "cp:settings:notifications:toggle"}],
        [{"text": "⚙️ Изменить важность", "callback_data": "cp:settings:notifications:level"}],
        [{"text": "⬅️ Настройки", "callback_data": "settings:menu"}],
    ]}

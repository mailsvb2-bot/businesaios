"""Business admin sub-dispatch split out of business_flow_ops (catalog, ads, retention)."""

from __future__ import annotations

from application.business_flows.projection import flow_payloads

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
        "offering_direction",
        "formats",
        "format_on",
        "format_off",
        "profile",
        "profile_set",
    }
)


def _catalog(done, op, arg, facts_):
    """Directions / offerings / formats; archive keeps history (catalog.py)."""
    from application.business_flows import catalog as cg

    c = cg.replay(facts_)
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
        return done("🗄 Убрано из активных; история сохранена.", cg.retire_offering(c, arg))
    if op in {"format_on", "format_off"}:
        ch = cg.toggle_format(c, arg, enabled=op == "format_on")
        return done(("✅ Формат обновлён." if ch else "Уже так.") + "\n" + cg.formats_text(c), ch)
    if op == "formats":
        return done(cg.formats_text(c))
    if op == "profile_set":
        return done("✅ Профиль обновлён.", cg.save_profile(c, arg))
    if op == "profile":
        return done(cg.profile_text(c))
    return done(cg.offerings_text(c))


def _ads(body, done, st, op, arg, facts_, sl_replay=None):
    """Governed ad proposals: drafts, exact-cap consent via approvals, publish gated by connector truth."""
    from application.business_flows import ad_proposals as ap
    from interfaces.ads.registry import CONNECTORS
    from runtime.platform.config.env_flags import env_str

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
    if op in {"ad_stats", "ad_report"}:
        from application.business_flows import ad_analytics as aa

        if op == "ad_stats":
            return done("📈 Статистика записана. /ad_report", aa.record(drafts, arg))
        leads = list(sl_replay().leads.values())
        return done(aa.report(drafts, aa.replay(facts_), leads))
    if op == "ad_creatives":  # advisory only: never changes provider budget/allocation
        return done(_creatives_text(arg))
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
    from application.business_flows import admin as ad
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
    from application.business_flows import catalog as cg

    c = cg.replay(flow_payloads(event_store, tenant_id=tenant_id, event_type="business_admin@v1"))
    change = bk.parse_slot(arg, now_ms=now, tz=c.timezone)
    title, offering_id = cg.resolve_slot_title(c, change["title"])
    if offering_id:
        change = {**change, "title": title, "offering_id": offering_id}
        change["slot_id"] = bk.stable_id("slot", change["starts_at_ms"], title)
    return change


def _sales_inbound(done, body, env, *, tenant_id, event_store):
    """Customer free text -> one lead_inbound fact (sales_intelligence); reply is the policy's text."""
    from application.business_flows import admin as ad
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
    from application.business_flows import catalog as cg
    from application.business_flows import sales as sl
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


def _promotions(done, bk, op, arg, now, slots, facts, *, user_id, tenant_id, event_store):
    """Slot promotions (donor ``promotions``): owner creates/refreshes, customer opens/books with attribution."""
    import secrets

    from application.business_flows import catalog as cg
    from application.business_flows import promotions as pm

    camps = pm.replay(facts)
    c = cg.replay(flow_payloads(event_store, tenant_id=tenant_id, event_type="business_admin@v1"))

    def line(slot_id: str) -> str:
        return bk.fmt(slots[slot_id], c.timezone) if slot_id in slots else "слот удалён"

    if op == "promotions":
        return done(pm.stats_text(camps, line), None)
    if op == "promote":
        n, _, channel = arg.partition(" ")
        opens = bk.upcoming(slots, now_ms=now, status="open")
        if not n.isdigit() or not 0 < int(n) <= len(opens):
            raise ValueError("/promote N [канал] — N из /slots")
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
        return done(
            f"📣 Кампания [{camp.channel}] готова. Ссылка: /start {pm.PREFIX}{camp.token}\n\n"
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
    from application.business_flows import catalog as cg
    from application.business_flows import event_notifications as en

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
        from application.business_flows.owner_panels import series_of

        if slot is None:
            raise ValueError("slot_not_found: /event_schedule N")
        series = series_of(slot, slots)
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
    from application.business_flows import event_channels as ec

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
    from application.business_flows import admin as ad
    from application.business_flows import event_series as es
    from application.business_flows import owner_panels as op_
    from application.business_flows import promotions as pr
    from application.business_flows import sales as sl

    def facts(t):
        return flow_payloads(event_store, tenant_id=tenant_id, event_type=t)

    leads = sl.replay(facts("sales_pipeline@v1")).leads.values()
    booked = {s.customer_id for s in slots.values() if s.customer_id}
    return op_.journey_text(
        leads=len(leads),
        slots=slots,
        attendance=es.replay(facts("event_series@v1")).attendance,
        payments=list(ad.replay(facts("business_admin@v1")).payments.values()),
        camps=pr.replay(facts("bookings@v1")),
        reactivated=sum(1 for x in leads if x.source.startswith("reactivation:") and x.customer_id in booked),
    )


def _panels(done, *a, **kw):
    """Owner read-only panels (owner_panels.py); never sends to customers, never spends."""
    try:
        return _panel(done, *a, **kw)
    except ValueError as exc:
        return done(f"📊 Не получилось: {exc}", None)


def _panel(done, bk, op, arg, now, slots, facts, *, tenant_id, event_store):
    from application.business_flows import owner_panels as op_
    from application.business_flows import promotions as pr
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
    slot, camps = live[int(n) - 1], pr.replay(facts)
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

    from application.business_flows import event_channels as ec
    from application.business_flows import event_notifications as en

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

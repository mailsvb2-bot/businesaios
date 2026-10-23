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
    if op == "ad_publish":
        truth = CONNECTORS["yandex_direct"]
        ready = bool(truth["production_ready"]) and bool(truth["requires_human_approval"])
        text, ch = ap.publish_decision(ap.by_ref(drafts, arg), st.approvals, production_ready=ready)
        return done(text, ch)
    return done(ap.list_text(drafts, st.approvals))


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

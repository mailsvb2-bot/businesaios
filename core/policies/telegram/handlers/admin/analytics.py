from __future__ import annotations

from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.handlers.admin.analytics_helpers import deny_if_not_admin, staff_reply
from core.policies.telegram.helpers import ProposedAction, propose
from core.ux.telegram_keyboards import kb_back_main, kb_staff_menu


def handle_analytics(ctx: TelegramCtx, *, user_id: str, pm) -> ProposedAction | None:
    if ctx.callback_data in {"admin:demo:brief", "admin:demo:full"}:
        denied = deny_if_not_admin(ctx.is_admin, pm=pm)
        if denied is not None:
            return denied
        ds = (ctx.admin_metrics.get("demo_summary") or {}) if isinstance(ctx.admin_metrics, dict) else {}
        sent_work = int(ds.get("sent_work") or 0)
        sent_home = int(ds.get("sent_home") or 0)
        users = int(ds.get("users") or 0)
        if ctx.callback_data.endswith("brief"):
            txt = (
                "📊 Сводка (кратко)\n\n"
                f"Пользователей (30д): {users}\n"
                f"Утро: {sent_work}\n"
                f"Вечер: {sent_home}\n"
            )
        else:
            txt = (
                "📈 Сводка (подробно)\n\n"
                f"Пользователей (30д): {users}\n"
                f"Всего отправок: {sent_work + sent_home}\n"
                f"Утро: {sent_work}\n"
                f"Вечер: {sent_home}\n\n"
                "ℹ️ Это best-effort аналитика по событиям отправки."
            )
        return staff_reply(pm=pm, text=txt)

    if ctx.callback_data == "admin:users:today":
        denied = deny_if_not_admin(ctx.is_admin, pm=pm)
        if denied is not None:
            return denied
        n = int((ctx.admin_metrics or {}).get("users_today") or 0)
        return pm(text=f"👥 Пользователи сегодня: {n}", reply_markup=kb_staff_menu())

    if ctx.callback_data == "admin:segments":
        denied = deny_if_not_admin(ctx.is_admin, pm=pm)
        if denied is not None:
            return denied
        from core.admin.read_model import segments_summary

        seg = segments_summary(ctx.event_store, days=30)
        txt = (
            "🧲 Сегменты (30д/7д)\n\n"
            f"🆕 Новые сегодня: {seg['new_users']}\n"
            f"🔥 Активные 7д: {seg['active_users_7d']}\n"
            f"💳 Плательщики 30д: {seg['payers_30d']}\n"
            f"✅ Доступ выдан 30д: {seg['granted_30d']}\n\n"
            "Подсказка: сегменты считаются по событиям (event-store), без второго мозга."
        )
        return pm(text=txt, reply_markup=kb_staff_menu())

    if ctx.callback_data == "admin:ab":
        if not ctx.is_admin:
            return pm(text="Доступ запрещён.", reply_markup=kb_back_main())
        from core.admin.read_model import ab_offers_summary

        ab = ab_offers_summary(ctx.event_store, days=30)
        txt = (
            "🧪 Тесты офферов (30д)\n\n"
            f"🧾 Сгенерировано вариантов: {ab['variants_set']}\n"
            f"✅ Выбрано вариантов: {ab['variants_chosen']}\n\n"
            "Совет: используйте «🤖 ИИ-копирайтер», затем выберите лучший вариант — он сохранится как событие."
        )
        return pm(text=txt, reply_markup=kb_staff_menu())

    if ctx.callback_data == "admin:giftshare":
        if not ctx.is_admin:
            return pm(text="Доступ запрещён.", reply_markup=kb_back_main())
        from core.admin.read_model import giftshare_summary

        gs = giftshare_summary(ctx.event_store, days=30)
        txt = (
            "🎁 Подарки и рекомендации (30д)\n\n"
            f"🔗 Переходы по приглашениям: {gs['share_clicked']}\n"
            f"🎁 Отправлено подарков: {gs['gift_sent']}\n\n"
            "Подсказка: события фиксируются в ledger → event-store."
        )
        return pm(text=txt, reply_markup=kb_staff_menu())

    if ctx.callback_data == "admin:funnel2":
        if not ctx.is_admin:
            return pm(text="Доступ запрещён.", reply_markup=kb_back_main())
        from core.admin.read_model import funnel2_report

        rep = funnel2_report(ctx.event_store, days=7)
        c = rep["counts"]
        r = rep["rates_pct_from_view"]
        txt = (
            "🧲 Воронка 2.0 (последние 7 дней)\n\n"
            f"👀 Просмотр тарифов: {c.get('tariffs_viewed',0)} (100%)\n"
            f"✅ Выбор тарифа: {c.get('tariff_selected',0)} ({r.get('tariff_selected',0)}%)\n"
            f"🧾 Создание оплаты: {c.get('payment_created',0)} ({r.get('payment_created',0)}%)\n"
            f"💳 Оплата успешна: {c.get('payment_captured',0)} ({r.get('payment_captured',0)}%)\n"
            f"🔓 Доступ выдан: {c.get('access_granted',0)} ({r.get('access_granted',0)}%)\n"
            f"📤 Первая отправка: {c.get('audio_sent',0)} ({r.get('audio_sent',0)}%)\n\n"
            "Воронка считается из event-store (DB fast-path), без второго мозга."
        )
        return pm(text=txt, reply_markup=kb_staff_menu())

    if ctx.callback_data == "admin:funnel":
        if not ctx.is_admin:
            return pm(text="Доступ запрещён.", reply_markup=kb_back_main())
        f = (ctx.admin_metrics.get("funnel") or {}) if isinstance(ctx.admin_metrics, dict) else {}
        txt = (
            "📉 Воронка (уникальные пользователи)\n\n"
            f"Тарифы: просмотрели — {int(f.get('tariffs_viewed') or 0)}\n"
            f"Тариф: выбрали — {int(f.get('tariff_selected') or 0)}\n"
            f"Оплата: создано — {int(f.get('payment_created') or 0)}\n"
            f"Оплата: успешно — {int(f.get('payment_succeeded') or 0)}\n"
            f"Доступ: выдан — {int(f.get('access_granted') or 0)}\n"
            f"Отправок контента: {int(f.get('audio_sent') or 0)}\n"
        )
        return pm(text=txt, reply_markup=kb_staff_menu())

    if ctx.callback_data == "admin:latency":
        if not ctx.is_admin:
            return pm(text="Доступ запрещён.", reply_markup=kb_back_main())
        lat = (ctx.admin_metrics.get("latency") or {}) if isinstance(ctx.admin_metrics, dict) else {}
        rows = lat.get("top_slowest") or []
        window = int(lat.get("window_days") or 7)
        samples = int(lat.get("samples") or 0)
        if not rows:
            return pm(text=f"⏱ Латентность кнопок\n\nДанных пока нет (окно {window}д).", reply_markup=kb_staff_menu())
        lines = [f"⏱ Латентность кнопок (окно {window}д)", f"Сэмплов: {samples}", ""]
        for r0 in rows[:10]:
            try:
                lines.append(
                    f"• {r0.get('button')} — p50 {int(r0.get('p50_ms') or 0)}мс, p95 {int(r0.get('p95_ms') or 0)}мс, max {int(r0.get('max_ms') or 0)}мс (n={int(r0.get('count') or 0)})"
                )
            except Exception:
                continue
        return pm(text="\n".join(lines), reply_markup=kb_staff_menu())

    if ctx.callback_data == "admin:retention":
        if not ctx.is_admin:
            return pm(text="Доступ запрещён.", reply_markup=kb_back_main())
        r = (ctx.admin_metrics.get("retention") or {}) if isinstance(ctx.admin_metrics, dict) else {}
        users = int(r.get("users") or 0)
        active_2d = int(r.get("active_2d") or 0)
        txt = (
            "🧩 Удержание (базово)\n\n"
            f"Пользователей (30д): {users}\n"
            f"Активны ≥2 дней (30д): {active_2d}\n\n"
            "ℹ️ Это proxy-метрика по событиям. Следующий шаг — retention по сценариям."
        )
        return pm(text=txt, reply_markup=kb_staff_menu())

    if ctx.callback_data == "admin:user:card":
        if not ctx.is_admin:
            return pm(text="Доступ запрещён.", reply_markup=kb_back_main())
        txt = (
            "🔎 Карточка пользователя\n\n"
            "Напиши команду:\n"
            "• /user <telegram_id>\n\n"
            "Пример: /user 123456789"
        )
        return pm(text=txt, reply_markup=kb_staff_menu())

    if ctx.callback_data == "admin:state:last":
        if not ctx.is_admin:
            return pm(text="Доступ запрещён.", reply_markup=kb_back_main())
        if not ctx.moods:
            return pm(text="Пока нет отмеченных состояний.", reply_markup=kb_staff_menu())
        out_lines = []
        for it in ctx.moods[-10:]:
            try:
                sc = it.get("score")
                note = (it.get("note") or "").strip()
                if note:
                    out_lines.append(f"• {sc}/10 — {note.replace(chr(10), ' ')[:80]}")
                else:
                    out_lines.append(f"• {sc}/10")
            except Exception:
                continue
        return pm(text="🧾 Последние состояния:\n" + "\n".join(out_lines), reply_markup=kb_staff_menu())

    if ctx.cmd == "/user":
        if not ctx.is_admin:
            return pm(text="Доступ запрещён.", reply_markup=kb_back_main())
        raw = (ctx.args or "").strip()
        if not raw:
            return pm(text="Используй: /user <telegram_id>", reply_markup=kb_staff_menu())
        target = raw.split()[0]
        if not target.isdigit():
            return pm(text="ID должен быть числом. Пример: /user 123456789", reply_markup=kb_staff_menu())
        return propose("admin_user_card@v1", {"admin_id": user_id, "target_user_id": str(target)})

    return None

"""Admin slash-commands.

This module intentionally contains *only* command parsing and formatting.
All irreversible actions must still go through propose(...) and Runtime.
"""

from __future__ import annotations

from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import ProposedAction
from core.ux.telegram_keyboards import kb_back_main, kb_staff_menu

ADMIN_COMMANDS = {"/admin", "/demo_stats", "/funnel", "/retention", "/latency", "/causal"}

def handle_admin_commands(ctx: TelegramCtx, *, pm) -> ProposedAction | None:
    """Handle admin informational commands.

    Returns ProposedAction if handled.
    """

    if ctx.cmd not in ADMIN_COMMANDS:
        return None

    if not ctx.is_admin:
        return pm(text="Недоступно.", reply_markup=kb_back_main())

    if ctx.cmd == "/admin":
        return pm(
            text=(
                "🛠 Админ\n\n"
                "Доступные команды:\n"
                "• /demo_stats — сводка\n"
                "• /funnel — воронка (уникальные пользователи)\n"
                "• /retention — базовая статистика удержания\n"
                "• /latency — скорость кнопок\n"
                "• /causal — evidence (причинность)\n\n"
                "Подсказка: удобнее пользоваться кнопкой «🛠 Панель» в меню."
            ),
            reply_markup=kb_staff_menu(),
        )

    if ctx.cmd == "/demo_stats":
        ds = (ctx.admin_metrics.get("demo_summary") or {}) if isinstance(ctx.admin_metrics, dict) else {}
        sent_work = int(ds.get("sent_work") or 0)
        sent_home = int(ds.get("sent_home") or 0)
        users = int(ds.get("users") or 0)
        txt = (
            "📊 Сводка\n\n"
            f"Пользователей (30д): {users}\n"
            f"Утро: {sent_work}\n"
            f"Вечер: {sent_home}\n\n"
            "ℹ️ Данные по событиям отправки контента."
        )
        return pm(text=txt, reply_markup=kb_staff_menu())

    if ctx.cmd == "/funnel":
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

    if ctx.cmd == "/causal":
        ce: dict = {}
        try:
            eco = dict(getattr(ctx.state, "economy", {}) or {})
            raw = eco.get("causal_evidence")
            ce = dict(raw or {}) if isinstance(raw, dict) else {}
        except Exception:
            ce = {}

        if not ce:
            return pm(
                text="🧪 Causal evidence\n\nДанных пока нет (нужны события за последние недели).",
                reply_markup=kb_staff_menu(),
            )

        def _fmt_pack(name: str, pack: dict) -> str:
            try:
                eff = float(pack.get("effect"))
            except Exception:
                eff = 0.0
            ci_low = pack.get("ci_low")
            ci_high = pack.get("ci_high")
            n_days = int(pack.get("n_days") or 0)
            placebo = pack.get("placebo_effect")
            return (
                f"• {name}: эффект {eff:.4f} (CI [{ci_low}, {ci_high}]), дней={n_days}\n"
                f"  placebo(shift+1d)={placebo}"
            )

        lines = ["🧪 Causal evidence (v1)", ""]
        if isinstance(ce.get("pricing"), dict):
            lines.append(_fmt_pack("Pricing → Payments", dict(ce.get("pricing") or {})))
        if isinstance(ce.get("ads"), dict):
            lines.append(_fmt_pack("Ads Apply → Payments", dict(ce.get("ads") or {})))
        lines.append("")
        lines.append("⚠️ Это evidence, не решение. Используй вместе с доменной экспертизой.")
        return pm(text="\n".join(lines), reply_markup=kb_staff_menu())

    if ctx.cmd == "/latency":
        lat = (ctx.admin_metrics.get("latency") or {}) if isinstance(ctx.admin_metrics, dict) else {}
        rows = lat.get("top_slowest") or []
        window = int(lat.get("window_days") or 7)
        samples = int(lat.get("samples") or 0)
        if not rows:
            return pm(text=f"⏱ Латентность кнопок\n\nДанных пока нет (окно {window}д).\n", reply_markup=kb_staff_menu())
        lines = [f"⏱ Латентность кнопок (окно {window}д)", f"Сэмплов: {samples}", ""]
        for r0 in rows[:10]:
            try:
                lines.append(
                    f"• {r0.get('button')} — p50 {int(r0.get('p50_ms') or 0)}мс, p95 {int(r0.get('p95_ms') or 0)}мс, max {int(r0.get('max_ms') or 0)}мс (n={int(r0.get('count') or 0)})"
                )
            except Exception:
                continue
        return pm(text="\n".join(lines), reply_markup=kb_staff_menu())

    # /retention
    r = (ctx.admin_metrics.get("retention") or {}) if isinstance(ctx.admin_metrics, dict) else {}
    users = int(r.get("users") or 0)
    active_2d = int(r.get("active_2d") or 0)
    txt = (
        "🧩 Удержание (базово)\n\n"
        f"Пользователей (30д): {users}\n"
        f"Активны ≥2 дней (30д): {active_2d}\n\n"
        "Идея следующего шага: отчёт по «пропустил N дней» на базе событий отправки."
    )
    return pm(text=txt, reply_markup=kb_staff_menu())

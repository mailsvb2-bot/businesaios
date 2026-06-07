from __future__ import annotations


from core.admin.read_model import latency_breakdown, latency_brief, sla_breaches_brief
from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import ProposedAction, propose_message


def admin_latency_report(ctx: TelegramCtx) -> ProposedAction:
    es = getattr(getattr(ctx, "env", None), "event_store", None)

    brief = latency_brief(es, days=7, limit=10)
    breakdown = latency_breakdown(es, days=7, limit=10)
    breaches = sla_breaches_brief(es, days=7, limit=3)

    lines = []
    lines.append("⏱ Латентность кнопок (7 дней)")
    lines.append(f"Сэмплов execute: {brief.get('samples', 0)}")
    lines.append("")

    top = brief.get("top_slowest") or []
    if top:
        lines.append("Топ (total execute, p95):")
        for r in top:
            lines.append(
                f"• {r.get('button')} — n={r.get('count')} p50={r.get('p50_ms')}ms p95={r.get('p95_ms')}ms max={r.get('max_ms')}ms"
            )
    else:
        lines.append("Нет данных по latency_span.")

    lines.append("")
    rows = breakdown.get("rows") or []
    if rows:
        lines.append("Разбивка по стадиям (p95):")
        for r in rows:
            lines.append(
                f"• {r.get('button')} — decide p95={r.get('decide_p95_ms',0)}ms, execute p95={r.get('execute_p95_ms',0)}ms, tg_api p95={r.get('telegram_api_p95_ms',0)}ms"
            )

    if breaches.get("breaches"):
        lines.append("")
        lines.append("⚠️ SLA watchdog (p95 ≥ budget):")
        for b in breaches["breaches"]:
            budget = b.get("budget_ms", 0)
            offenders = b.get("offenders") or []
            if not offenders:
                continue
            lines.append(f"Budget={budget}ms:")
            for o in offenders[:5]:
                lines.append(f"  - {o.get('button')} n={o.get('count')} p95={o.get('p95_ms')}ms")

    return propose_message(ctx, "\n".join(lines))

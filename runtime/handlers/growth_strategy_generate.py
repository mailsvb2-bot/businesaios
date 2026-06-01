from __future__ import annotations

CANON_THIN_HANDLER = True


from typing import Any, Dict

from runtime.growth import GrowthGoalV1, GrowthStrategyService
from runtime.ports.effects import EffectsPort

ACTION_NAME = "growth_strategy_generate@v1"


def handle_growth_strategy_generate(payload: dict[str, Any], effects: EffectsPort, env: Any, *, event_store: Any, llm: Any = None) -> Any:
    p = payload or {}
    tenant_id = str(p.get("tenant_id") or getattr(env, "tenant_id", "") or "")
    user_id = str(p.get("user_id") or "")
    decision_id = str(getattr(env, "decision", None).decision_id if getattr(env, "decision", None) else p.get("decision_id") or "")
    correlation_id = str(getattr(env, "decision", None).correlation_id if getattr(env, "decision", None) else p.get("correlation_id") or "")

    goal = _parse_goal(p.get("goal") or {})
    n = int(p.get("n") or 8)
    model = str(p.get("model") or "")

    svc = GrowthStrategyService(event_store=event_store, llm=llm)
    plan = svc.generate_backlog(tenant_id=tenant_id, user_id=user_id, decision_id=decision_id, correlation_id=correlation_id, goal=goal, n=n, model=model)

    return effects.send_message(
        decision_id=decision_id,
        correlation_id=correlation_id,
        user_id=user_id,
        text=_render_plan(plan),
        reply_markup=_menu_markup(),
        callback_query_id=p.get("callback_query_id"),
        critical=False,
        track_event_type=ACTION_NAME,
        track_payload={"tenant_id": tenant_id},
    )


def _parse_goal(d: dict[str, Any]) -> GrowthGoalV1:
    try:
        if not isinstance(d, dict):
            return GrowthGoalV1()
        base = GrowthGoalV1()
        return GrowthGoalV1(
            primary_stage=str(d.get("primary_stage") or base.primary_stage),  # type: ignore[arg-type]
            horizon_days=int(d.get("horizon_days") or base.horizon_days),
            kpi=str(d.get("kpi") or base.kpi),
            target_delta_pct=float(d.get("target_delta_pct") or base.target_delta_pct),
            constraints=tuple(d.get("constraints") or base.constraints),
        )
    except Exception:
        return GrowthGoalV1()


def _render_plan(plan) -> str:
    s = plan.signals
    lines = []
    lines.append("🧠 AI Growth Strategy — backlog гипотез")
    lines.append("")
    lines.append(f"Сегодня: лиды={s.leads_today}, spend={s.spend_today_minor}, revenue={s.revenue_today_minor}, profit={s.profit_today_minor}")
    lines.append(f"Retention: D1={s.retention_d1_pct:.1f}%, D7={s.retention_d7_pct:.1f}% | Конверсия lead→purchase={s.conversion_lead_to_purchase_pct:.1f}%")
    if s.top_channels:
        lines.append("Топ-каналы: " + ", ".join(s.top_channels))
    lines.append("")
    for i, h in enumerate(plan.top_hypotheses[:8], 1):
        lines.append(f"{i}) [{h.stage}/{h.channel}] {h.title}")
        if h.expected_impact:
            lines.append(f"   эффект: {h.expected_impact}")
        if h.mechanism:
            lines.append(f"   почему: {h.mechanism}")
        lines.append(f"   effort={h.effort}, risk={h.risk}, metric={h.metric}, horizon={h.horizon_days}d")
        lines.append(f"   id={h.hypothesis_id}")
        lines.append("")
    lines.append("Дальше: открой backlog и прими/отклони гипотезы.")
    return "\n".join(lines).strip()


def _menu_markup() -> dict[str, Any]:
    return {"inline_keyboard": [[{"text": "📋 Backlog", "callback_data": "growth:backlog"}], [{"text": "🔁 Сгенерировать ещё", "callback_data": "growth:generate"}]]}

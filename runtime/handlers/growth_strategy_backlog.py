from __future__ import annotations

CANON_THIN_HANDLER = True


from typing import Any

from runtime.growth import GrowthStrategyService
from runtime.ports.effects import EffectsPort

ACTION_NAME = "growth_strategy_backlog@v1"


def handle_growth_strategy_backlog(payload: dict[str, Any], effects: EffectsPort, env: Any, *, event_store: Any) -> Any:
    p = payload or {}
    tenant_id = str(p.get("tenant_id") or getattr(env, "tenant_id", "") or "")
    user_id = str(p.get("user_id") or "")
    decision_id = str(getattr(env, "decision", None).decision_id if getattr(env, "decision", None) else p.get("decision_id") or "")
    correlation_id = str(getattr(env, "decision", None).correlation_id if getattr(env, "decision", None) else p.get("correlation_id") or "")

    svc = GrowthStrategyService(event_store=event_store, llm=None)
    backlog = svc.backlog(tenant_id=tenant_id, limit=int(p.get("limit") or 30))

    text, markup = _render_backlog(backlog)
    return effects.send_message(
        decision_id=decision_id,
        correlation_id=correlation_id,
        user_id=user_id,
        text=text,
        reply_markup=markup,
        callback_query_id=p.get("callback_query_id"),
        critical=False,
        track_event_type=ACTION_NAME,
        track_payload={"tenant_id": tenant_id},
    )


def _render_backlog(backlog):
    lines = ["📋 Growth Backlog", ""]
    kb = []
    for i, (h, s, state) in enumerate(backlog[:20], 1):
        score = f"{s.score:.0f}" if s else "-"
        lines.append(f"{i}) {h.title}  (score={score}, state={state})")
        lines.append(f"   [{h.stage}/{h.channel}] metric={h.metric} horizon={h.horizon_days}d")
        lines.append(f"   id={h.hypothesis_id}")
        kb.append([{"text": f"✅ Принять {i}", "callback_data": f"growth:accept:{h.hypothesis_id}"}, {"text": "❌", "callback_data": f"growth:reject:{h.hypothesis_id}"}])
    kb.append([{"text": "⬅️ Назад", "callback_data": "growth:menu"}])
    return "\n".join(lines).strip(), {"inline_keyboard": kb}

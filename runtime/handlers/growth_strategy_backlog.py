from __future__ import annotations

from typing import Any

from runtime.growth import GrowthStrategyService
from runtime.handlers.delivery_contract import delivery_kwargs
from runtime.ports.effects import EffectsPort

CANON_THIN_HANDLER = True
ACTION_NAME = "growth_strategy_backlog@v1"


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise RuntimeError(f"{key.upper()}_REQUIRED")
    return value


def handle_growth_strategy_backlog(payload: dict[str, Any], effects: EffectsPort, env: Any, *, event_store: Any) -> Any:
    body = dict(payload or {})
    tenant_id = _required_text(body, "tenant_id")
    user_id = _required_text(body, "user_id")
    decision_id = str(env.decision.decision_id)
    correlation_id = str(env.decision.correlation_id)

    service = GrowthStrategyService(event_store=event_store, llm=None)
    backlog = service.backlog(
        tenant_id=tenant_id,
        limit=int(body.get("limit") or 30),
    )

    text, markup = _render_backlog(backlog)
    return effects.send_message(
        decision_id=decision_id,
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        user_id=user_id,
        text=text,
        reply_markup=markup,
        callback_query_id=body.get("callback_query_id"),
        critical=False,
        track_event_type=ACTION_NAME,
        track_payload={"tenant_id": tenant_id},
        **delivery_kwargs(body),
    )


def _render_backlog(backlog):
    lines = ["📋 Growth Backlog", ""]
    keyboard = []
    for index, (hypothesis, score, state) in enumerate(backlog[:20], 1):
        score_text = f"{score.score:.0f}" if score else "-"
        lines.append(f"{index}) {hypothesis.title}  (score={score_text}, state={state})")
        lines.append(
            f"   [{hypothesis.stage}/{hypothesis.channel}] metric={hypothesis.metric} horizon={hypothesis.horizon_days}d"
        )
        lines.append(f"   id={hypothesis.hypothesis_id}")
        keyboard.append(
            [
                {
                    "text": f"✅ Принять {index}",
                    "callback_data": f"growth:accept:{hypothesis.hypothesis_id}",
                },
                {
                    "text": "❌",
                    "callback_data": f"growth:reject:{hypothesis.hypothesis_id}",
                },
            ]
        )
    keyboard.append([{"text": "⬅️ Назад", "callback_data": "growth:menu"}])
    return "\n".join(lines).strip(), {"inline_keyboard": keyboard}

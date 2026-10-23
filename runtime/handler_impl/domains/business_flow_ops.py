"""Handlers for event-sourced business flows (application.business_flows).

Each handler replays the flow from the Event Store, applies one pure
transition and records it as the tracked event of the delivered reply, so a
transition exists iff the user-visible receipt exists.
"""

from __future__ import annotations

from typing import Any

from application.business_flows import bot_provisioning as botprov
from application.business_flows.projection import flow_payloads
from runtime.handler_impl.core.payloads import require_mapping, required_str
from runtime.handler_impl.domains.admin_ops import _card_outcome
from runtime.handlers.delivery_contract import delivery_kwargs


def send_tracked(body, effects, env, *, text: str, event_type: str | None, event_payload: dict[str, Any] | None,
                 ok: bool = True, reason: str = "") -> dict[str, Any]:
    tenant_id, user_id = required_str(body, "tenant_id"), required_str(body, "user_id")
    tracked = dict(event_payload or {}) if event_type else None
    if tracked is not None:
        tracked.update(tenant_id=tenant_id, user_id=user_id)
    delivery = effects.send_message(
        decision_id=env.decision.decision_id, correlation_id=env.decision.correlation_id,
        tenant_id=tenant_id, user_id=user_id, text=text, reply_markup=None,
        track_event_type=event_type, track_payload=tracked, **delivery_kwargs(body),
    )
    return _card_outcome(delivery=delivery, ok=ok, reason=reason)


_BOT_STATUS_RU = {
    "awaiting_secret": "ожидает токен (передайте его через защищённую форму владельца)",
    "ready": "токен получен, ожидает проверки",
    "verifying": "идёт проверка бота",
    "completed": "подключён",
    "failed": "ошибка проверки — можно повторить",
    "cancelled": "отменён",
}


def handle_bot_provisioning(payload, effects, env, *, event_store):
    body = require_mapping(payload or {})
    tenant_id, user_id = required_str(body, "tenant_id"), required_str(body, "user_id")
    op, arg = str(body.get("op") or "status"), str(body.get("arg") or "")
    state = botprov.replay(flow_payloads(event_store, tenant_id=tenant_id, event_type="bot_provisioning@v1"))
    current = botprov.active(state)
    try:
        if op == "request":
            change = botprov.request(state, tenant_id=tenant_id, user_id=user_id, username=arg)
            text = f"🤖 Заявка на подключение @{change['username']} создана.\nСтатус: {_BOT_STATUS_RU['awaiting_secret']}"
        elif op == "cancel":
            if current is None:
                raise ValueError("bot_provisioning_not_found")
            change = botprov.transition(current, "cancel")
            text = f"🤖 Подключение @{current.username} отменено."
        else:
            change = None
            text = ("🤖 Активных подключений нет.\nСоздать: /connect_bot имя_бота" if current is None
                    else f"🤖 @{current.username}: {_BOT_STATUS_RU[current.status.value]}")
    except ValueError as exc:
        return send_tracked(body, effects, env, text=f"🤖 Не получилось: {exc}", event_type=None,
                            event_payload=None, ok=True, reason="")
    return send_tracked(body, effects, env, text=text, event_type="bot_provisioning@v1" if change else None,
                        event_payload=change)


__all__ = ["handle_bot_provisioning", "send_tracked"]

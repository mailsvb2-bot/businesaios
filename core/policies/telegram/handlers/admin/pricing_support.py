from __future__ import annotations

from typing import Any


def back_markup(callback_data: str) -> dict[str, list[list[dict[str, str]]]]:
    return {"inline_keyboard": [[{"text": "⬅️ Назад", "callback_data": str(callback_data)}]]}


def pricing_session_payload(*, user_id: str, stage: str, callback_query_id: str | None, back_to: str, **value: Any) -> dict[str, Any]:
    session_value = {"stage": str(stage)}
    session_value.update(value)
    return {
        "user_id": str(user_id),
        "key": "admin:pricing_session",
        "value": session_value,
        "callback_query_id": callback_query_id,
        "notify_reply_markup": back_markup(back_to),
    }


def ai_request_rows(*, plan_id: int, suggested_price: int) -> dict[str, list[list[dict[str, str]]]]:
    return {
        "inline_keyboard": [
            [{"text": f"📝 Создать request → {int(suggested_price)}₽", "callback_data": f"admin:pricing:ai_request:{int(plan_id)}:{int(suggested_price)}"}],
            [{"text": "⬅️ Назад", "callback_data": "admin:pricing:menu"}],
        ]
    }


def pending_rows(*, request_id: str) -> list[list[dict[str, str]]]:
    rid = str(request_id)
    return [[
        {"text": f"✅ Approve {rid[:8]}", "callback_data": f"admin:pricing:approve:{rid}"},
        {"text": f"❌ Reject {rid[:8]}", "callback_data": f"admin:pricing:reject:{rid}"},
    ]]




def pricing_edit_request_payload(*, user_id: str, plan_id: int, callback_query_id: str | None) -> dict[str, Any]:
    payload = pricing_session_payload(
        user_id=user_id,
        stage="await_price",
        callback_query_id=callback_query_id,
        back_to="admin:pricing:menu",
        plan_id=int(plan_id),
    )
    payload["notify_text"] = (
        f"💸 Изменение цены для тарифа #{int(plan_id)}.\n\n"
        "Введи новую цену (руб), можно с версией: `2290 v20.1`\n"
        "Отмена: отправь `cancel`"
    )
    return payload


def pricing_approve_request_payload(*, user_id: str, request_id: str, callback_query_id: str | None) -> dict[str, Any]:
    rid = str(request_id).strip()
    payload = pricing_session_payload(
        user_id=user_id,
        stage="await_approve_version",
        callback_query_id=callback_query_id,
        back_to="admin:pricing:pending",
        request_id=rid,
    )
    payload["notify_text"] = (
        "✅ Подтверждение change-request\n\n"
        f"Request: {rid}\n"
        "Введи PRICING_VERSION для применения (например: v20.1).\n"
        "Отмена: `cancel`"
    )
    return payload


def parse_plan_callback_id(callback_data: str, *, prefix: str) -> int | None:
    if not isinstance(callback_data, str) or not callback_data.startswith(prefix):
        return None
    try:
        return int(callback_data.split(":")[-1])
    except Exception:
        return None


def parse_ai_request_callback(callback_data: str) -> tuple[int, int] | None:
    if not isinstance(callback_data, str) or not callback_data.startswith("admin:pricing:ai_request:"):
        return None
    try:
        parts = callback_data.split(":")
        return int(parts[3]), int(parts[4])
    except Exception:
        return None


def pending_requests_view(requests: list[dict[str, Any]]) -> tuple[str, dict[str, list[list[dict[str, str]]]]]:
    pending = [r for r in requests if str(r.get("status")) == "pending"]
    if not pending:
        return "✅ Нет pending change-request'ов.", back_markup("admin:pricing:menu")
    rows: list[list[dict[str, str]]] = []
    lines = ["🕒 Pending pricing change-requests\n"]
    for r in pending[:10]:
        rid = str(r.get("request_id") or "")
        pid = int(r.get("plan_id") or 0)
        price = int(r.get("new_price") or 0)
        sv = str(r.get("suggested_pricing_version") or "").strip()
        who = str(r.get("requested_by") or "")
        lines.append(f"• #{pid} → {price}₽  (req={rid[:8]}) by {who} {('v='+sv) if sv else ''}")
        rows.extend(pending_rows(request_id=rid))
    rows.append([{"text": "⬅️ Назад", "callback_data": "admin:pricing:menu"}])
    return "\n".join(lines), {"inline_keyboard": rows}


__all__ = ["ai_request_rows", "back_markup", "pending_rows", "pricing_session_payload", "pricing_edit_request_payload", "pricing_approve_request_payload", "parse_plan_callback_id", "parse_ai_request_callback", "pending_requests_view"]

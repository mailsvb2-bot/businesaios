from __future__ import annotations

from typing import Any

_ALLOWED_INLINE_PLAN_ACTIONS = frozenset({"noop@v1"})


def extract_ids(payload: Any) -> tuple[str, str]:
    if not isinstance(payload, dict):
        return ("unknown", "unknown")
    return (str(payload.get("tenant_id") or "unknown"), str(payload.get("user_id") or "unknown"))


def require_idempotency_key(*, spec: Any, payload: Any) -> None:
    if not bool(getattr(spec, "requires_idempotency_key", False)):
        return
    if not isinstance(payload, dict):
        raise RuntimeError("MISSING_IDEMPOTENCY_KEY")
    ik = payload.get("idempotency_key")
    if not isinstance(ik, str) or not ik.strip():
        raise RuntimeError("MISSING_IDEMPOTENCY_KEY")


def validate_execute_plan_payload(*, action: str, payload: Any, schemas: Any) -> None:
    if str(action) != "execute_plan@v1":
        return
    if not isinstance(payload, dict):
        raise RuntimeError("INVALID_EXECUTE_PLAN_PAYLOAD")
    steps = payload.get("steps")
    if not isinstance(steps, list):
        raise RuntimeError("INVALID_EXECUTE_PLAN_STEPS")
    if len(steps) > 50:
        raise RuntimeError("EXECUTE_PLAN_TOO_LARGE")
    for step in steps:
        if not isinstance(step, dict):
            raise RuntimeError("INVALID_EXECUTE_PLAN_STEP")
        step_action = str(step.get("action") or "")
        if not step_action:
            raise RuntimeError("MISSING_EXECUTE_PLAN_STEP_ACTION")
        if step_action == "execute_plan@v1":
            raise RuntimeError("NESTED_EXECUTE_PLAN_FORBIDDEN")
        if step_action not in _ALLOWED_INLINE_PLAN_ACTIONS:
            raise RuntimeError("EXECUTE_PLAN_STEP_REQUIRES_SEPARATE_DECISION_ENVELOPE")
        step_ver = int(step.get("action_schema_version") or 0)
        if step_ver <= 0:
            raise RuntimeError("MISSING_EXECUTE_PLAN_STEP_VERSION")
        step_payload = {k: v for k, v in step.items() if k not in {"action", "action_schema_version"}}
        schemas.validate(step_action, step_payload, version=step_ver)


def validate_telegram_transport_payload(*, action: str, payload: Any, run_mode: str) -> None:
    if run_mode != "telegram" or str(action) != "send_message@v1":
        return
    if not isinstance(payload, dict):
        raise RuntimeError("INVALID_PAYLOAD_TYPE")
    channel = str(payload.get("channel") or "telegram").strip().lower().replace("-", "_")
    aliases = {
        "facebook": "messenger",
        "facebook_messenger": "messenger",
        "instagram_dm": "instagram",
        "web": "web_chat",
        "widget": "web_chat",
        "kakao": "kakaotalk",
    }
    channel = aliases.get(channel, channel)
    if channel != "telegram":
        return
    uid = payload.get("user_id")
    if not isinstance(uid, str) or not uid.isdigit() or int(uid) <= 0:
        raise RuntimeError("TELEGRAM_CHAT_ID_REQUIRED")

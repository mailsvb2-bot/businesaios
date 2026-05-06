from __future__ import annotations

from kernel.world_state import WorldStateV1


def extract_session_fields(state: WorldStateV1) -> dict[str, object]:
    session = dict(getattr(state, "session", {}) or {})
    cbq_id = session.get("callback_query_id") if bool(session.get("is_callback")) else None
    callback_query_id = str(cbq_id) if cbq_id is not None else None
    return {
        "text": str(session.get("text") or "").strip(),
        "cmd": session.get("command"),
        "args": str(session.get("args") or ""),
        "callback_data": str(session.get("callback_data") or "") if bool(session.get("is_callback")) else "",
        "callback_query_id": callback_query_id,
    }


def extract_user_fields(state: WorldStateV1) -> dict[str, object]:
    user = dict(getattr(state, "user", {}) or {})
    settings = dict(user.get("settings") or {}) if isinstance(user.get("settings"), dict) else {}
    return {
        "settings": settings,
        "city": str(user.get("city") or settings.get("city") or ""),
        "moods": list(user.get("mood_last") or []) if isinstance(user.get("mood_last"), list) else [],
        "admin_metrics": dict(user.get("admin_metrics") or {}) if isinstance(user.get("admin_metrics"), dict) else {},
        "selected_tariff": dict(user.get("selected_tariff") or {}) if isinstance(user.get("selected_tariff"), dict) else {},
        "marketing_variants": dict(user.get("marketing_variants") or {}) if isinstance(user.get("marketing_variants"), dict) else {},
        "marketing_seed": str(user.get("marketing_seed") or "1"),
        "marketing_bandit": dict(user.get("marketing_bandit") or {}) if isinstance(user.get("marketing_bandit"), dict) else {},
        "roles": list(user.get("roles") or []) if isinstance(user.get("roles"), list) else [],
        "perms": list(user.get("perms") or []) if isinstance(user.get("perms"), list) else [],
        "realtime_state": dict(user.get("realtime_state") or {}) if isinstance(user.get("realtime_state"), dict) else {},
        "autopilot_dashboard": dict(user.get("autopilot_dashboard") or {}) if isinstance(user.get("autopilot_dashboard"), dict) else {},
        "pricing_suggestions": dict(user.get("pricing_suggestions") or {}) if isinstance(user.get("pricing_suggestions"), dict) else {},
    }

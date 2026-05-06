from __future__ import annotations

from typing import Any, Dict, Tuple


def load_user_profile(event_store: Any, *, tenant_id: str, user_id: str) -> Tuple[Dict[str, Any], str, Any, list[Any]]:
    try:
        from core.users.read_model import user_settings, user_city, selected_tariff, mood_last
        settings = user_settings(event_store, tenant_id=str(tenant_id), user_id=user_id)
        city = user_city(event_store, tenant_id=str(tenant_id), user_id=user_id)
        tariff = selected_tariff(event_store, tenant_id=str(tenant_id), user_id=user_id)
        moods = mood_last(event_store, tenant_id=str(tenant_id), user_id=user_id, limit=10)
        return settings, city, tariff, moods
    except Exception:
        return {}, "", None, []

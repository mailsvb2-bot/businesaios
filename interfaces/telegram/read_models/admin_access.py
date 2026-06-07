from __future__ import annotations

from typing import Any

from interfaces.telegram.read_models.components.admin_metrics import load_admin_metrics
from runtime.platform.config.env_flags import env_csv


def is_superadmin(chat_id: str) -> bool:
    try:
        admins = set(env_csv("ADMIN_USER_IDS")) | set(env_csv("ADMIN_IDS"))
        return str(chat_id) in admins
    except Exception:
        return False


def resolve_admin_metrics(*, is_admin: bool, event_store: Any, tenant_id: str, enrich_admin_metrics: Any) -> dict[str, Any]:
    if is_admin:
        return enrich_admin_metrics()
    try:
        from core.admin.read_model import users_today
        return {"users_today": int(users_today(event_store, tenant_id=str(tenant_id)))}
    except Exception:
        return {"users_today": 0}


__all__ = ["is_superadmin", "resolve_admin_metrics", "load_admin_metrics"]

"""Admin roles & permissions (event-sourced read models).

This module is READ-ONLY.

Strict tenant contract:
- every read must pass tenant_id explicitly to the event store
- no silent defaults inside iter_events
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

ROLE_ADMIN = "admin"
ROLE_MARKETING = "marketing"

def _iter(event_store: Any, *, tenant_id: str, event_type: str) -> Iterable[dict[str, Any]]:
    if event_store is None or not hasattr(event_store, "iter_events"):
        return []
    return event_store.iter_events(tenant_id=str(tenant_id), start_ms=0, end_ms=None, event_type=str(event_type))


def roles_for_user(event_store: Any, *, tenant_id: str = "default", user_id: str) -> set[str]:
    user_id = str(user_id)
    roles: dict[str, bool] = {}
    for ev in _iter(event_store, tenant_id=tenant_id, event_type="admin_role_set"):
        p = ev.get("payload") or {}
        if str(p.get("target_user_id") or "") != user_id:
            continue
        role = str(p.get("role") or "").strip()
        if not role:
            continue
        enabled = bool(p.get("enabled", True))
        roles[role] = enabled
    return {r for r, on in roles.items() if on}


def perms_for_user(event_store: Any, *, tenant_id: str = "default", user_id: str) -> set[str]:
    user_id = str(user_id)
    perms: dict[str, bool] = {}
    for ev in _iter(event_store, tenant_id=tenant_id, event_type="admin_perm_set"):
        p = ev.get("payload") or {}
        if str(p.get("target_user_id") or "") != user_id:
            continue
        perm = str(p.get("perm") or "").strip()
        if not perm:
            continue
        enabled = bool(p.get("enabled", True))
        perms[perm] = enabled
    return {x for x, on in perms.items() if on}


def team_roles_snapshot(event_store: Any, *, tenant_id: str = "default") -> dict[str, list[str]]:
    """Return {user_id: [roles...]} for all users with any role."""
    by_user: dict[str, dict[str, bool]] = {}
    for ev in _iter(event_store, tenant_id=tenant_id, event_type="admin_role_set"):
        p = ev.get("payload") or {}
        uid = str(p.get("target_user_id") or "").strip()
        role = str(p.get("role") or "").strip()
        if not uid or not role:
            continue
        enabled = bool(p.get("enabled", True))
        by_user.setdefault(uid, {})[role] = enabled
    out: dict[str, list[str]] = {}
    for uid, m in by_user.items():
        out[uid] = sorted([r for r, on in m.items() if on])
    return out


def team_perms_snapshot(event_store: Any, *, tenant_id: str = "default") -> dict[str, list[str]]:
    by_user: dict[str, dict[str, bool]] = {}
    for ev in _iter(event_store, tenant_id=tenant_id, event_type="admin_perm_set"):
        p = ev.get("payload") or {}
        uid = str(p.get("target_user_id") or "").strip()
        perm = str(p.get("perm") or "").strip()
        if not uid or not perm:
            continue
        enabled = bool(p.get("enabled", True))
        by_user.setdefault(uid, {})[perm] = enabled
    out: dict[str, list[str]] = {}
    for uid, m in by_user.items():
        out[uid] = sorted([r for r, on in m.items() if on])
    return out

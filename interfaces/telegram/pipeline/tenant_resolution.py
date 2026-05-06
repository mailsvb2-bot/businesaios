from __future__ import annotations

from core.tenancy.request_context import get_tenant_id
from interfaces.telegram.pipeline.tenant_session_store import TenantSessionStore
from interfaces.telegram.pipeline.tenant_token import parse_tenant_token

_TENANT_SESSIONS = TenantSessionStore(ttl_s=6*3600)

def resolve_tenant_for_update(*, chat_id: str, user_id: str, text: str) -> str:
    token = parse_tenant_token(text or "")
    if token:
        return str(_TENANT_SESSIONS.bind(chat_id=str(chat_id), user_id=str(user_id), tenant_id=str(token)))
    existing = _TENANT_SESSIONS.get(chat_id=str(chat_id), user_id=str(user_id))
    if existing:
        return str(existing)
    return str(get_tenant_id())

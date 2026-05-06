from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from connectors.platform.ads.token_store import OAuthToken


class AsyncTokenStoreAdapter:
    """Async adapter over a sync token store.

    Connectors are async; our default token store is a small sqlite3-based
    component guarded by a lock. To keep connectors simple and avoid threads in
    handlers, we adapt via `asyncio.to_thread`.
    """

    def __init__(self, sync_store: Any):
        self._sync = sync_store

    async def put(self, *, tenant_id: str, platform: Any, account_id: str, token: Dict[str, Any]) -> None:
        t = OAuthToken(
            access_token=str(token.get("access_token") or ""),
            refresh_token=(str(token.get("refresh_token")) if token.get("refresh_token") else None),
            expires_at_iso=(str(token.get("expires_at_iso")) if token.get("expires_at_iso") else None),
            token_type=str(token.get("token_type") or "Bearer"),
            scope=(str(token.get("scope")) if token.get("scope") else None),
        )
        await asyncio.to_thread(self._sync.put, tenant_id=tenant_id, platform=str(getattr(platform, "value", platform)), account_id=account_id, token=t)

    async def get(self, *, tenant_id: str, platform: Any, account_id: str) -> Optional[Dict[str, Any]]:
        res = await asyncio.to_thread(self._sync.get, tenant_id=tenant_id, platform=str(getattr(platform, "value", platform)), account_id=account_id)
        if not res:
            return None
        return {
            "access_token": res.access_token,
            "refresh_token": res.refresh_token,
            "expires_at_iso": res.expires_at_iso,
            "token_type": res.token_type,
            "scope": res.scope,
        }

    async def delete(self, *, tenant_id: str, platform: Any, account_id: str) -> None:
        await asyncio.to_thread(self._sync.delete, tenant_id=tenant_id, platform=str(getattr(platform, "value", platform)), account_id=account_id)


# Backward-compatible alias for the canonical name used elsewhere.
# Keep a single implementation to avoid "second logic".
AdsTokenStoreAdapter = AsyncTokenStoreAdapter

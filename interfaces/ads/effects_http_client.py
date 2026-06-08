from __future__ import annotations

from typing import Any

from runtime.effects import http_get, http_post


class EffectsHTTPClient:
    """HTTPClient adapter powered by runtime.effects.

    This keeps network dependencies out of boot wiring.
    """

    async def get(self, url: str, *, headers: dict[str, str], params: dict[str, str] | None = None) -> dict[str, Any]:
        r = await http_get(url=url, headers=headers or {}, params=params or {})
        if isinstance(r.json, dict):
            return r.json
        # Non-JSON responses are treated as an error envelope.
        return {"status": r.status, "text": r.text}

    async def post(self, url: str, *, headers: dict[str, str], data: dict[str, Any] | None = None) -> dict[str, Any]:
        r = await http_post(url=url, headers=headers or {}, data=data or {})
        if isinstance(r.json, dict):
            return r.json
        return {"status": r.status, "text": r.text}

from __future__ import annotations

from collections.abc import Mapping

from runtime import effects as runtime_effects


class CrmOAuthQueryClient:
    """Small secret-conscious OAuth helper for providers with query-token endpoints.

    It routes I/O through the public runtime effects facade and intentionally
    reports only status/shape failures so client secrets never become part of a
    provider exception message.
    """

    def __init__(self, *, timeout_seconds: int = 20) -> None:
        if timeout_seconds <= 0:
            raise ValueError('OAuth timeout_seconds must be positive')
        self._timeout_seconds = int(timeout_seconds)

    def get_json(self, *, url: str, params: Mapping[str, object]) -> Mapping[str, object]:
        response = runtime_effects.http_get(
            url=url,
            headers={'Accept': 'application/json'},
            params=dict(params),
            timeout_s=self._timeout_seconds,
        )
        status = int(getattr(response, 'status', 0) or 0)
        payload = getattr(response, 'json', None)
        if status < 200 or status >= 300:
            raise RuntimeError(f'OAuth token endpoint returned HTTP {status or "unknown"}')
        if not isinstance(payload, Mapping):
            raise RuntimeError('OAuth token endpoint returned an invalid JSON object')
        if payload.get('error'):
            raise RuntimeError(f'OAuth token endpoint rejected request: {payload.get("error")}')
        return payload


__all__ = ['CrmOAuthQueryClient']

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol

from interfaces.ads.errors import ValidationError


class HTTPClient(Protocol):
    async def get(self, url: str, *, headers: Dict[str, str], params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]: ...

    async def post(self, url: str, *, headers: Dict[str, str], data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]: ...


@dataclass(frozen=True)
class OAuthTokenExchangeResult:
    access_token: str
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    raw: Optional[Dict[str, Any]] = None


class OAuthExchanger(Protocol):
    async def exchange(self, *, code: str, redirect_uri: str) -> OAuthTokenExchangeResult: ...


@dataclass(frozen=True)
class OAuthClientConfig:
    token_url: str
    client_id: str
    client_secret: str


class MetaOAuthExchanger:
    """Meta OAuth token exchange.

    Canonical: relies on the repo's HTTP client port (typically EffectsHTTPClient)
    and therefore keeps network libs inside sealed effects.

    Note: Meta token exchange uses GET with query params.
    """

    def __init__(self, *, http: HTTPClient, cfg: OAuthClientConfig) -> None:
        self._http = http
        self._cfg = cfg

    async def exchange(self, *, code: str, redirect_uri: str) -> OAuthTokenExchangeResult:
        if not code:
            raise ValidationError("missing code", field="code")
        raw = await self._http.get(
            self._cfg.token_url,
            headers={},
            params={
                "client_id": self._cfg.client_id,
                "client_secret": self._cfg.client_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            },
        )
        tok = raw.get("access_token")
        if not tok:
            raise ValidationError("token exchange failed", field="access_token")
        return OAuthTokenExchangeResult(
            access_token=str(tok),
            expires_in=_int_or_none(raw.get("expires_in")),
            raw=raw if isinstance(raw, dict) else None,
        )


class YandexOAuthExchanger:
    """Yandex.Direct OAuth exchange.

    Uses POST with form fields.
    """

    def __init__(self, *, http: HTTPClient, cfg: OAuthClientConfig) -> None:
        self._http = http
        self._cfg = cfg

    async def exchange(self, *, code: str, redirect_uri: str) -> OAuthTokenExchangeResult:
        if not code:
            raise ValidationError("missing code", field="code")
        raw = await self._http.post(
            self._cfg.token_url,
            headers={},
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self._cfg.client_id,
                "client_secret": self._cfg.client_secret,
                "redirect_uri": redirect_uri,
            },
        )
        tok = raw.get("access_token")
        if not tok:
            raise ValidationError("token exchange failed", field="access_token")
        return OAuthTokenExchangeResult(
            access_token=str(tok),
            refresh_token=_str_or_none(raw.get("refresh_token")),
            expires_in=_int_or_none(raw.get("expires_in")),
            raw=raw if isinstance(raw, dict) else None,
        )


class VkOAuthExchanger:
    """VK OAuth exchange.

    VK may return token as access_token_key.
    """

    def __init__(self, *, http: HTTPClient, cfg: OAuthClientConfig) -> None:
        self._http = http
        self._cfg = cfg

    async def exchange(self, *, code: str, redirect_uri: str) -> OAuthTokenExchangeResult:
        if not code:
            raise ValidationError("missing code", field="code")
        raw = await self._http.get(
            self._cfg.token_url,
            headers={},
            params={
                "client_id": self._cfg.client_id,
                "client_secret": self._cfg.client_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            },
        )
        tok = raw.get("access_token") or raw.get("access_token_key")
        if not tok:
            raise ValidationError("token exchange failed", field="access_token")
        return OAuthTokenExchangeResult(
            access_token=str(tok),
            expires_in=_int_or_none(raw.get("expires_in")),
            raw=raw if isinstance(raw, dict) else None,
        )


def _str_or_none(x: Any) -> Optional[str]:
    return str(x) if x is not None else None


def _int_or_none(x: Any) -> Optional[int]:
    try:
        return int(x) if x is not None else None
    except Exception:
        return None

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from interfaces.ads.base import OAuthAuthorizeURL


def _pct_encode(s: str) -> str:
    # RFC3986 unreserved: ALPHA / DIGIT / "-" / "." / "_" / "~"
    out: list[str] = []
    for b in s.encode("utf-8"):
        ch = chr(b)
        if (
            "A" <= ch <= "Z"
            or "a" <= ch <= "z"
            or "0" <= ch <= "9"
            or ch in "-._~"
        ):
            out.append(ch)
        else:
            out.append(f"%{b:02X}")
    return "".join(out)


def _query(params: dict[str, str]) -> str:
    parts: list[str] = []
    for k, v in params.items():
        parts.append(f"{_pct_encode(str(k))}={_pct_encode(str(v))}")
    return "&".join(parts)


@dataclass(frozen=True)
class OAuthAuthorizeParams:
    base_url: str
    client_id: str
    redirect_uri: str
    scope: str
    state: str
    response_type: str = "code"
    extra: dict[str, str] | None = None


def build_authorize_url(p: OAuthAuthorizeParams) -> OAuthAuthorizeURL:
    """Canonical builder to avoid duplicated connect() code across connectors."""
    q = {
        "client_id": p.client_id,
        "redirect_uri": p.redirect_uri,
        "state": p.state,
        "scope": p.scope,
        "response_type": p.response_type,
    }
    if p.extra:
        for k, v in p.extra.items():
            if v is None:
                continue
            q[str(k)] = str(v)

    base = p.base_url
    sep = "&" if "?" in base else "?"
    url = base + sep + _query(q)
    return OAuthAuthorizeURL(url=url, state=p.state)

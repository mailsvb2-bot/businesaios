from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from interfaces.ads.errors import ValidationError
from runtime.effects import url_with_params


@dataclass(frozen=True)
class OAuthAppConfig:
    authorize_url: str
    token_url: str
    client_id: str
    client_secret: str
    scopes: str
    extra_auth_params: Optional[Dict[str, str]] = None


def build_authorization_url(*, cfg: OAuthAppConfig, redirect_uri: str, state: str) -> str:
    """Build an OAuth authorization URL without importing URL-encoding helpers.

    Query encoding is delegated to the sealed effects implementation to preserve
    the repo-wide rule: query encoding must happen only in
    `runtime/_internal/_effects_impl.py`.
    """

    if not cfg.authorize_url or not cfg.client_id:
        raise ValidationError("OAuth config missing", field="client_id")

    params: Dict[str, str] = {
        "client_id": cfg.client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "state": state,
    }
    if cfg.scopes:
        params["scope"] = cfg.scopes
    if cfg.extra_auth_params:
        params.update({k: str(v) for k, v in cfg.extra_auth_params.items()})

    return url_with_params(url=cfg.authorize_url, params=params)

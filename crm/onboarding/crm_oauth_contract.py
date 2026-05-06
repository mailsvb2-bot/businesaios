from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class CrmOAuthStartRequest:
    tenant_id: str
    business_id: str
    provider_key: str
    redirect_uri: str
    state_token: str
    scopes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CrmOAuthCallbackPayload:
    provider_key: str
    state_token: str
    authorization_code: str
    metadata: Mapping[str, object] = field(default_factory=dict)

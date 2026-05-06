from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class CrmConnectionRef:
    tenant_id: str
    business_id: str
    provider_key: str
    connection_id: str
    status: str = 'pending'
    secret_ref: str | None = None
    external_account_id: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

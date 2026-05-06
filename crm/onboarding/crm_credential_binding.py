from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CrmCredentialBinding:
    secret_ref: str
    token_binding_ref: str
    provider_key: str

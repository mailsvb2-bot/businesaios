from __future__ import annotations

from datetime import datetime

from typing import Iterable, Protocol

from security.key_management_contract import KeyMaterialRecord, KeyPurpose

CANON_KEY_PROVIDER_CONTRACTS = True


class KeyProvider(Protocol):
    def issue_key(
        self,
        *,
        key_id: str,
        purpose: KeyPurpose,
        tenant_id: str | None = None,
        connector_id: str | None = None,
        expires_in_seconds: int | None = None,
    ) -> KeyMaterialRecord: ...

    def register(self, record: KeyMaterialRecord) -> None: ...

    def get(self, key_id: str) -> KeyMaterialRecord: ...

    def get_active_for(
        self,
        *,
        purpose: KeyPurpose,
        tenant_id: str | None = None,
        connector_id: str | None = None,
        at: datetime | None = None,
    ) -> KeyMaterialRecord: ...


__all__ = ["CANON_KEY_PROVIDER_CONTRACTS", "KeyProvider"]

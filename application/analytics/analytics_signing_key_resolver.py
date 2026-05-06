from __future__ import annotations

from dataclasses import dataclass

from security.key_management_contract import KeyPurpose
from security.key_provider import KeyProvider, build_default_key_provider


@dataclass(frozen=True)
class AnalyticsSigningKeyResolver:
    key_provider: KeyProvider | None = None

    def _provider(self) -> KeyProvider:
        return self.key_provider or build_default_key_provider()

    def resolve_or_issue(self, *, tenant_id: str, key_id_hint: str = "analytics-export-signing") -> tuple[str, str]:
        provider = self._provider()
        try:
            record = provider.get_active_for(purpose=KeyPurpose.REQUEST_SIGNING, tenant_id=str(tenant_id))
        except KeyError:
            record = provider.issue_key(
                key_id=f"{key_id_hint}-{tenant_id}-v1",
                purpose=KeyPurpose.REQUEST_SIGNING,
                tenant_id=str(tenant_id),
            )
        return str(record.key_id), bytes(record.secret_bytes).hex()

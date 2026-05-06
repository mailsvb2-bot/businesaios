from __future__ import annotations

from crm.crm_identity_contract import CrmIdentity


class ProviderIdentityMapper:
    def to_provider_identity(self, identity: CrmIdentity) -> dict[str, object]:
        return {'canonical_key': identity.canonical_key, 'email': identity.email, 'phone': identity.phone}

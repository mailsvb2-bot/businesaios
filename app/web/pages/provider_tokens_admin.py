from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from shared.kinded_payloads import build_kinded_payload

CANON_WEB_PROVIDER_TOKENS_ADMIN_PAGE = True


@dataclass(frozen=True, slots=True)
class ProviderTokensAdminPage:
    kind: str = 'provider_tokens_admin_page'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        return build_kinded_payload(self.kind, {'title': 'Provider workspace moved', 'deprecated': True, 'replacement_path': '/business-workspace/providers', 'tenant_bound': True, 'write_actions_enabled': False})


__all__ = ['CANON_WEB_PROVIDER_TOKENS_ADMIN_PAGE', 'ProviderTokensAdminPage']

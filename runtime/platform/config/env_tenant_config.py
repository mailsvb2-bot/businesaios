from __future__ import annotations

from typing import Optional

from runtime.platform.config.env_flags import env_str


class EnvTenantConfigStore:
    def get(self, *, tenant_id: str, key: str) -> Optional[str]:
        tid = _norm(tenant_id)
        value = env_str(f"TENANT_{tid}__{key}", "")
        return value if value else None


def _norm(s: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in s.upper())

from __future__ import annotations


from runtime.platform.config.env_flags import env_str


class EnvTenantConfigStore:
    def get(self, *, tenant_id: str, key: str) -> str | None:
        tid = _norm(tenant_id)
        value = env_str(f"TENANT_{tid}__{key}", "")
        return value if value else None


def _norm(s: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in s.upper())

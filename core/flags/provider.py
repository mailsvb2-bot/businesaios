from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol

from config.env_flags import env_bool, env_csv
from core.tenancy.scope import TenantId


@dataclass(frozen=True)
class FlagContext:
    tenant_id: TenantId
    user_id: str | None = None
    attributes: dict[str, Any] | None = None


class FeatureFlagProvider(Protocol):
    def enabled(self, flag: str, *, ctx: FlagContext) -> bool: ...


class EnvFlagProvider:
    """Minimal provider: reads flags from environment variables.

    Convention:
      FLAG_<NAME>=1/0
      FLAG_<NAME>_TENANTS=tenantA,tenantB

    This is intentionally dumb; production should plug a real provider.
    """

    def enabled(self, flag: str, *, ctx: FlagContext) -> bool:
        name = (flag or "").strip().upper()
        if not name:
            return False
        base = env_bool(f"FLAG_{name}", False)
        if not base:
            return False
        tenants = set(env_csv(f"FLAG_{name}_TENANTS"))
        if not tenants:
            return True
        return str(ctx.tenant_id) in tenants

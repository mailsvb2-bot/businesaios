"""Generic kill switch (feature-flag driven).

Why this exists:
  - Ads already has an in-memory kill switch.
  - Runtime needs a *global*, tenant-scoped kill switch that can block whole
    classes of actions (ads / payments / llm / general) before side-effects.

Convention (env-based default provider):
  FLAG_KILL_<KIND>=1 enables the kill switch (execution is blocked).
  Optional tenant allowlist:
    FLAG_KILL_<KIND>_TENANTS=tenantA,tenantB
"""

from __future__ import annotations

from dataclasses import dataclass

from core.flags.provider import FeatureFlagProvider, FlagContext


@dataclass(frozen=True)
class KillSwitchState:
    kind: str
    killed: bool


class KillSwitch:
    def __init__(self, flags: FeatureFlagProvider):
        self._flags = flags

    def is_killed(self, kind: str, *, tenant_id: str, user_id: str | None = None) -> bool:
        k = str(kind or "").strip().upper()
        if not k:
            return False
        ctx = FlagContext(tenant_id=str(tenant_id), user_id=str(user_id) if user_id is not None else None)
        return bool(self._flags.enabled(f"KILL_{k}", ctx=ctx))

    def state(self, kind: str, *, tenant_id: str, user_id: str | None = None) -> KillSwitchState:
        return KillSwitchState(kind=str(kind), killed=self.is_killed(kind, tenant_id=str(tenant_id), user_id=user_id))

    def require_allowed(self, kind: str, *, tenant_id: str, user_id: str | None = None) -> None:
        if self.is_killed(kind, tenant_id=str(tenant_id), user_id=user_id):
            raise RuntimeError(f"KILL_SWITCHED kind={str(kind)}")

from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

from config.env_flags import env_str

TenantId = NewType("TenantId", str)


def as_tenant_id(value: str | TenantId | "TenantScope") -> TenantId:
    """Convert to TenantId with strict non-empty validation."""
    if isinstance(value, TenantScope):
        v = value.tenant_id
    else:
        v = str(value or "")
    v = v.strip()
    if not v:
        raise ValueError("tenant_id is required (non-empty)")
    v = v.replace("/", "_").replace("\\", "_")
    return TenantId(v)


@dataclass(frozen=True)
class TenantScope:
    """First-class tenant scope.

    TenantScope is the *only* sanctioned way to carry tenant_id through runtime.
    It enforces non-empty, stable, filesystem-safe tenant identifiers.
    """

    tenant_id: str

    def __post_init__(self) -> None:
        tid = str(self.tenant_id or "").strip()
        if not tid:
            raise ValueError("tenant_id is required (non-empty)")
        tid = tid.replace("/", "_").replace("\\", "_")
        object.__setattr__(self, "tenant_id", tid)

    @classmethod
    def from_env(cls) -> "TenantScope":
        tid = env_str("TENANT_ID", "").strip()
        if tid:
            return cls(tenant_id=tid)

        run_mode = env_str("RUN_MODE", env_str("MODE", "demo")).strip().lower()
        env_name = env_str("ENV", "dev").strip().lower()
        if run_mode == "demo" or env_name in {"dev", "local", "test"}:
            return cls(tenant_id="demo")

        raise ValueError("TENANT_ID env is required (tenant strict mode)")

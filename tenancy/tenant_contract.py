from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Mapping, Protocol, TYPE_CHECKING

from core.tenancy.normalization import normalize_tenant_id, require_tenant_id

if TYPE_CHECKING:
    from tenancy.tenant_policy_store import TenantPolicyBundle


CANON_TENANCY_CONTRACT = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TenantStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DISABLED = "disabled"
    DELETING = "deleting"


class TenantPlan(str, Enum):
    INTERNAL = "internal"
    FREE = "free"
    STARTER = "starter"
    GROWTH = "growth"
    ENTERPRISE = "enterprise"


@dataclass(frozen=True)
class TenantRecord:
    tenant_id: str
    display_name: str
    status: TenantStatus = TenantStatus.ACTIVE
    plan: TenantPlan = TenantPlan.STARTER
    created_at: datetime = field(default_factory=utc_now)
    billing_account_id: str | None = None
    data_region: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)
    aliases: tuple[str, ...] = ()

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.display_name or "").strip():
            raise ValueError("display_name is required")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        normalized_aliases = {
            normalize_tenant_id(item)
            for item in self.aliases
            if normalize_tenant_id(item)
        }
        if require_tenant_id(self.tenant_id) in normalized_aliases:
            raise ValueError("aliases must not duplicate tenant_id")


@dataclass(frozen=True)
class TenantQuotaCheck:
    allowed: bool
    reason: str
    tenant_id: str
    dimension: str
    requested: float
    used: float
    limit: float | None = None
    remaining: float | None = None
    retry_after_seconds: int | None = None


class TenantRegistryContract(Protocol):
    def register(self, record: TenantRecord) -> TenantRecord: ...
    def get(self, tenant_id: str) -> TenantRecord | None: ...
    def require(self, tenant_id: str) -> TenantRecord: ...
    def resolve(self, tenant_hint: str) -> TenantRecord | None: ...
    def list_active(self) -> tuple[TenantRecord, ...]: ...


class TenantPolicyStoreContract(Protocol):
    def get(self, tenant_id: str) -> "TenantPolicyBundle | None": ...
    def require(self, tenant_id: str) -> "TenantPolicyBundle": ...
    def save(self, bundle: "TenantPolicyBundle") -> "TenantPolicyBundle": ...


class TenantQuotaGuardContract(Protocol):
    def check(
        self,
        *,
        tenant_id: str,
        dimension: str,
        amount: float = 1.0,
    ) -> TenantQuotaCheck: ...

    def consume(
        self,
        *,
        tenant_id: str,
        dimension: str,
        amount: float = 1.0,
    ) -> TenantQuotaCheck: ...

    def reset(self, *, tenant_id: str, dimension: str | None = None) -> None: ...


__all__ = [
    "CANON_TENANCY_CONTRACT",
    "TenantPlan",
    "TenantPolicyStoreContract",
    "TenantQuotaCheck",
    "TenantQuotaGuardContract",
    "TenantRecord",
    "TenantRegistryContract",
    "TenantStatus",
    "utc_now",
]

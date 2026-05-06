from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from core.tenancy.normalization import require_tenant_id


CANON_TENANT_FEATURE_FLAGS = True


@dataclass(frozen=True)
class TenantFeatureFlags:
    tenant_id: str
    flags: Mapping[str, bool] = field(default_factory=dict)
    variants: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        for key in self.flags.keys():
            if not str(key or "").strip():
                raise ValueError("feature flag keys must be non-empty")
        for key in self.variants.keys():
            if not str(key or "").strip():
                raise ValueError("variant keys must be non-empty")

    def is_enabled(self, flag_name: str, *, default: bool = False) -> bool:
        self.validate()
        name = str(flag_name or "").strip()
        if not name:
            raise ValueError("flag_name is required")
        return bool(self.flags.get(name, default))

    def variant(self, flag_name: str, *, default: str | None = None) -> str | None:
        self.validate()
        name = str(flag_name or "").strip()
        if not name:
            raise ValueError("flag_name is required")
        value = self.variants.get(name)
        if value is None:
            return default
        return str(value)

    def merged_with(self, other: "TenantFeatureFlags") -> "TenantFeatureFlags":
        if require_tenant_id(self.tenant_id) != require_tenant_id(other.tenant_id):
            raise ValueError("cross-tenant flag merge is forbidden")
        merged_flags = {str(k): bool(v) for k, v in self.flags.items()}
        merged_flags.update({str(k): bool(v) for k, v in other.flags.items()})
        merged_variants = {str(k): str(v) for k, v in self.variants.items()}
        merged_variants.update({str(k): str(v) for k, v in other.variants.items()})
        return TenantFeatureFlags(
            tenant_id=self.tenant_id,
            flags=merged_flags,
            variants=merged_variants,
        )


__all__ = ["CANON_TENANT_FEATURE_FLAGS", "TenantFeatureFlags"]

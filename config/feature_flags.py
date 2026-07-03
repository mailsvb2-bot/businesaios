from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from config.environment_matrix import normalize_environment_name
from core.tenancy.normalization import normalize_tenant_id
from tenancy.tenant_feature_flags import TenantFeatureFlags

CANON_COMPAT_SHIM = True

CANON_CONFIG_FEATURE_FLAGS = True


@dataclass(frozen=True)
class FeatureFlagSnapshot:
    scope_name: str
    environment: str
    flags: Mapping[str, bool] = field(default_factory=dict)
    variants: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.scope_name or "").strip():
            raise ValueError("scope_name is required")
        if not normalize_environment_name(self.environment):
            raise ValueError("environment is required")
        for key in self.flags:
            if not str(key or "").strip():
                raise ValueError("flag keys must be non-empty")
        for key in self.variants:
            if not str(key or "").strip():
                raise ValueError("variant keys must be non-empty")

    def merged_with(self, other: FeatureFlagSnapshot) -> FeatureFlagSnapshot:
        self.validate()
        other.validate()
        if normalize_environment_name(self.environment) != normalize_environment_name(other.environment):
            raise ValueError("feature flag snapshots from different environments cannot be merged")
        flags = {str(k): bool(v) for k, v in self.flags.items()}
        flags.update({str(k): bool(v) for k, v in other.flags.items()})
        variants = {str(k): str(v) for k, v in self.variants.items()}
        variants.update({str(k): str(v) for k, v in other.variants.items()})
        return FeatureFlagSnapshot(
            scope_name=f"{self.scope_name}+{other.scope_name}",
            environment=self.environment,
            flags=flags,
            variants=variants,
        )


class ConfigFeatureFlagResolver:
    """Canonical flag read path.

    Merge precedence is fixed and explicit:
    environment defaults -> config snapshot -> tenant overrides.
    """

    def __init__(
        self,
        *,
        environment_snapshot: FeatureFlagSnapshot,
        config_snapshot: FeatureFlagSnapshot | None = None,
        tenant_snapshots: Mapping[str, TenantFeatureFlags] | None = None,
    ) -> None:
        environment_snapshot.validate()
        if config_snapshot is not None:
            config_snapshot.validate()
        if config_snapshot is not None and normalize_environment_name(environment_snapshot.environment) != normalize_environment_name(config_snapshot.environment):
            raise ValueError("config_snapshot must match environment_snapshot environment")
        self._environment_snapshot = environment_snapshot
        self._config_snapshot = config_snapshot
        self._tenant_snapshots = {
            normalize_tenant_id(tenant_id): snapshot
            for tenant_id, snapshot in dict(tenant_snapshots or {}).items()
            if normalize_tenant_id(tenant_id)
        }

    def with_tenant_flags(self, snapshot: TenantFeatureFlags) -> ConfigFeatureFlagResolver:
        snapshot.validate()
        tenant_snapshots = dict(self._tenant_snapshots)
        tenant_snapshots[normalize_tenant_id(snapshot.tenant_id)] = snapshot
        return ConfigFeatureFlagResolver(
            environment_snapshot=self._environment_snapshot,
            config_snapshot=self._config_snapshot,
            tenant_snapshots=tenant_snapshots,
        )

    def is_enabled(self, flag_name: str, *, tenant_id: str | None = None, default: bool = False) -> bool:
        name = str(flag_name or "").strip()
        if not name:
            raise ValueError("flag_name is required")
        merged = self.merged_flags_for(tenant_id=tenant_id)
        if name in merged:
            return bool(merged[name])
        return bool(default)

    def variant(self, flag_name: str, *, tenant_id: str | None = None, default: str | None = None) -> str | None:
        name = str(flag_name or "").strip()
        if not name:
            raise ValueError("flag_name is required")
        merged = self.merged_variants_for(tenant_id=tenant_id)
        if name not in merged:
            return default
        return str(merged[name])

    def merged_flags_for(self, *, tenant_id: str | None = None) -> dict[str, bool]:
        merged = {str(k): bool(v) for k, v in self._environment_snapshot.flags.items()}
        if self._config_snapshot is not None:
            merged.update({str(k): bool(v) for k, v in self._config_snapshot.flags.items()})
        tenant_flags = self._tenant_snapshot_or_none(tenant_id)
        if tenant_flags is not None:
            merged.update({str(k): bool(v) for k, v in tenant_flags.flags.items()})
        return merged

    def merged_variants_for(self, *, tenant_id: str | None = None) -> dict[str, str]:
        merged = {str(k): str(v) for k, v in self._environment_snapshot.variants.items()}
        if self._config_snapshot is not None:
            merged.update({str(k): str(v) for k, v in self._config_snapshot.variants.items()})
        tenant_flags = self._tenant_snapshot_or_none(tenant_id)
        if tenant_flags is not None:
            merged.update({str(k): str(v) for k, v in tenant_flags.variants.items()})
        return merged

    def _tenant_snapshot_or_none(self, tenant_id: str | None) -> TenantFeatureFlags | None:
        normalized = normalize_tenant_id(tenant_id)
        if not normalized:
            return None
        return self._tenant_snapshots.get(normalized)


__all__ = [
    "CANON_CONFIG_FEATURE_FLAGS",
    "ConfigFeatureFlagResolver",
    "FeatureFlagSnapshot",
]

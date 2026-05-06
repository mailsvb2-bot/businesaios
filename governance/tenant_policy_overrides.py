from __future__ import annotations

"""
Tenant-scoped policy overrides.

Rules:
- Overrides may tighten policy.
- Overrides may add only low-risk read visibility permissions.
- Overrides must never create an alternative decision authority.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from contracts.action_impact_contract import ActionCategory
from core.tenancy.normalization import require_tenant_id
from governance.control_plane_audit_log import GovernanceAuditEvent, GovernanceAuditLogContract, NullGovernanceAuditLog
from governance.persistence_codec import atomic_write_json, from_dataclass, read_json_or_default, to_jsonable
from governance.persistence_paths import tenant_policy_override_store_path
from governance.rbac_contract import Permission


CANON_GOVERNANCE_TENANT_POLICY_OVERRIDES = True


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


_ALLOWED_ADDITIVE_PERMISSIONS = frozenset({
    Permission.VIEW_AUDIT,
    Permission.VIEW_APPROVALS,
    Permission.VIEW_POLICY,
})


@dataclass(frozen=True)
class TenantPolicyOverride:
    tenant_id: str
    add_permissions: frozenset[Permission] = field(default_factory=frozenset)
    remove_permissions: frozenset[Permission] = field(default_factory=frozenset)
    blocked_action_names: frozenset[str] = field(default_factory=frozenset)
    blocked_categories: frozenset[str] = field(default_factory=frozenset)
    force_approval_for_categories: frozenset[str] = field(default_factory=frozenset)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)

        overlapping_permissions = self.add_permissions & self.remove_permissions
        if overlapping_permissions:
            raise ValueError(
                "same permission may not appear in both add_permissions and remove_permissions: "
                + ", ".join(sorted(x.value for x in overlapping_permissions))
            )

        disallowed_additions = self.add_permissions - _ALLOWED_ADDITIVE_PERMISSIONS
        if disallowed_additions:
            raise ValueError(
                "tenant policy override may not grant powerful permissions: "
                + ", ".join(sorted(x.value for x in disallowed_additions))
            )

        valid_categories = {item.value for item in ActionCategory}
        unknown_blocked = set(self.blocked_categories) - valid_categories
        if unknown_blocked:
            raise ValueError("unknown blocked_categories: " + ", ".join(sorted(unknown_blocked)))

        unknown_forced = set(self.force_approval_for_categories) - valid_categories
        if unknown_forced:
            raise ValueError("unknown force_approval_for_categories: " + ", ".join(sorted(unknown_forced)))

        for action_name in self.blocked_action_names:
            if not str(action_name or "").strip():
                raise ValueError("blocked_action_names must not contain empty values")


class TenantPolicyOverrideRegistry:
    def __init__(self) -> None:
        self._items: dict[str, TenantPolicyOverride] = {}

    def put(self, override: TenantPolicyOverride) -> None:
        override.validate()
        self._items[require_tenant_id(override.tenant_id)] = override

    def remove(self, tenant_id: str) -> None:
        self._items.pop(require_tenant_id(tenant_id), None)

    def get(self, tenant_id: str) -> TenantPolicyOverride | None:
        return self._items.get(require_tenant_id(tenant_id))

    def effective_permissions(
        self,
        *,
        tenant_id: str,
        base_permissions: frozenset[Permission],
    ) -> frozenset[Permission]:
        override = self.get(tenant_id)
        if override is None:
            return base_permissions
        return frozenset((set(base_permissions) | set(override.add_permissions)) - set(override.remove_permissions))

    def is_action_blocked(self, *, tenant_id: str, action_name: str, category: str | None) -> bool:
        override = self.get(tenant_id)
        if override is None:
            return False
        normalized_action = str(action_name or "").strip()
        normalized_category = str(category or "").strip()
        return (
            normalized_action in override.blocked_action_names
            or normalized_category in override.blocked_categories
        )

    def forces_approval(self, *, tenant_id: str, category: str | None) -> bool:
        override = self.get(tenant_id)
        if override is None:
            return False
        return str(category or "").strip() in override.force_approval_for_categories


class PersistentTenantPolicyOverrideRegistry(TenantPolicyOverrideRegistry):
    """Durable tenant policy override registry backed by JSON data."""

    def __init__(
        self,
        path: str | Path | None = None,
        audit_log: GovernanceAuditLogContract | None = None,
    ) -> None:
        self._path = Path(path) if path is not None else tenant_policy_override_store_path()
        self._audit_log = audit_log or NullGovernanceAuditLog()
        super().__init__()
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    def put(self, override: TenantPolicyOverride) -> None:
        super().put(override)
        self._flush()
        self._emit_audit(
            event_type="tenant_policy_override_upserted",
            tenant_id=override.tenant_id,
            payload={
                "tenant_id": override.tenant_id,
                "blocked_categories": sorted(override.blocked_categories),
                "force_approval_for_categories": sorted(override.force_approval_for_categories),
            },
        )

    def remove(self, tenant_id: str) -> None:
        tid = require_tenant_id(tenant_id)
        existing = self._items.get(tid)
        super().remove(tid)
        self._flush()
        if existing is not None:
            self._emit_audit(
                event_type="tenant_policy_override_removed",
                tenant_id=tid,
                payload={"tenant_id": tid},
            )

    def _load(self) -> None:
        raw = read_json_or_default(self._path, default={"overrides": []})
        items = raw.get("overrides", []) if isinstance(raw, dict) else []
        loaded: dict[str, TenantPolicyOverride] = {}
        for item in items:
            override = from_dataclass(TenantPolicyOverride, item)
            override.validate()
            loaded[override.tenant_id] = override
        self._items = loaded

    def _flush(self) -> None:
        atomic_write_json(
            self._path,
            {"overrides": [to_jsonable(item) for item in self._items.values()]},
        )

    def _emit_audit(self, *, event_type: str, tenant_id: str, payload: dict[str, object]) -> None:
        self._audit_log.append(
            GovernanceAuditEvent(
                event_type=event_type,
                tenant_id=tenant_id,
                emitted_at=_utc_now(),
                payload=payload,
            )
        )


__all__ = [
    "CANON_GOVERNANCE_TENANT_POLICY_OVERRIDES",
    "TenantPolicyOverride",
    "TenantPolicyOverrideRegistry",
    "PersistentTenantPolicyOverrideRegistry",
]

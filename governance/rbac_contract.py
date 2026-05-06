from __future__ import annotations

"""
Canonical RBAC contract.

Important constraints:
- This layer does NOT choose business strategy.
- This layer does NOT replace DecisionCore.
- This layer only answers whether an actor is permitted to perform,
  approve, stop, inspect, or override within strict governance bounds.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Protocol


CANON_GOVERNANCE_RBAC_CONTRACT = True


class Permission(str, Enum):
    VIEW_AUDIT = "view_audit"
    VIEW_APPROVALS = "view_approvals"
    VIEW_POLICY = "view_policy"

    EXECUTE_SAFE_READ = "execute_safe_read"
    EXECUTE_INTERNAL_WRITE = "execute_internal_write"
    EXECUTE_OUTBOUND = "execute_outbound"
    EXECUTE_PUBLICATION = "execute_publication"
    EXECUTE_BUDGET_CHANGE = "execute_budget_change"
    EXECUTE_STRATEGIC_CHANGE = "execute_strategic_change"
    EXECUTE_ROLLBACK = "execute_rollback"
    EXECUTE_GENERIC_EXECUTION = "execute_generic_execution"

    APPROVE_CHANGE = "approve_change"
    APPROVE_FINANCE_CHANGE = "approve_finance_change"
    APPROVE_PRODUCTION_CHANGE = "approve_production_change"

    ACTIVATE_KILL_SWITCH = "activate_kill_switch"
    RELEASE_KILL_SWITCH = "release_kill_switch"

    MANAGE_TENANT_POLICY = "manage_tenant_policy"


class RoleId(str, Enum):
    SYSTEM = "system"
    OWNER = "owner"
    OPERATOR = "operator"
    ANALYST = "analyst"
    FINANCE = "finance"
    AUDITOR = "auditor"
    SECURITY = "security"
    SUPPORT = "support"
    VIEWER = "viewer"


@dataclass(frozen=True)
class ActorContext:
    actor_id: str
    tenant_id: str
    role_ids: frozenset[RoleId] = field(default_factory=frozenset)
    is_service: bool = False
    attributes: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.actor_id or "").strip():
            raise ValueError("actor_id is required")
        if not str(self.tenant_id or "").strip():
            raise ValueError("tenant_id is required")


@dataclass(frozen=True)
class ResourceRef:
    resource_type: str
    resource_id: str
    tenant_id: str
    attributes: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.resource_type or "").strip():
            raise ValueError("resource_type is required")
        if not str(self.resource_id or "").strip():
            raise ValueError("resource_id is required")
        if not str(self.tenant_id or "").strip():
            raise ValueError("tenant_id is required")


@dataclass(frozen=True)
class AccessRequest:
    actor: ActorContext
    permission: Permission
    resource: ResourceRef | None = None
    action_name: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        self.actor.validate()
        if self.resource is not None:
            self.resource.validate()
            if self.resource.tenant_id != self.actor.tenant_id:
                raise ValueError("cross-tenant access request is forbidden")


@dataclass(frozen=True)
class AccessVerdict:
    allowed: bool
    reason: str
    matched_roles: tuple[RoleId, ...] = ()
    effective_permissions: frozenset[Permission] = field(default_factory=frozenset)
    operator_required: bool = False
    audit_fields: Mapping[str, object] = field(default_factory=dict)


class RoleCatalogContract(Protocol):
    def is_known_role(self, role_id: RoleId) -> bool: ...
    def normalize_roles(self, role_ids: frozenset[RoleId]) -> frozenset[RoleId]: ...


class PermissionMatrixContract(Protocol):
    def permissions_for_role(self, role_id: RoleId) -> frozenset[Permission]: ...
    def permission_for_action_category(self, category: str) -> Permission | None: ...


__all__ = [
    "AccessRequest",
    "AccessVerdict",
    "ActorContext",
    "CANON_GOVERNANCE_RBAC_CONTRACT",
    "Permission",
    "PermissionMatrixContract",
    "ResourceRef",
    "RoleCatalogContract",
    "RoleId",
]

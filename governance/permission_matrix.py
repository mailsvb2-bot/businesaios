from __future__ import annotations

"""Canonical permission matrix.
This module must remain declarative.
"""

from contracts.action_impact_contract import ActionCategory
from governance.rbac_contract import Permission, PermissionMatrixContract, RoleId


CANON_GOVERNANCE_PERMISSION_MATRIX = True


_ROLE_PERMISSIONS: dict[RoleId, frozenset[Permission]] = {
    RoleId.SYSTEM: frozenset({
        Permission.VIEW_AUDIT,
        Permission.VIEW_APPROVALS,
        Permission.VIEW_POLICY,
        Permission.EXECUTE_SAFE_READ,
        Permission.EXECUTE_INTERNAL_WRITE,
        Permission.EXECUTE_GENERIC_EXECUTION,
    }),
    RoleId.OWNER: frozenset({
        Permission.VIEW_AUDIT,
        Permission.VIEW_APPROVALS,
        Permission.VIEW_POLICY,
        Permission.EXECUTE_SAFE_READ,
        Permission.EXECUTE_INTERNAL_WRITE,
        Permission.EXECUTE_OUTBOUND,
        Permission.EXECUTE_PUBLICATION,
        Permission.EXECUTE_BUDGET_CHANGE,
        Permission.EXECUTE_STRATEGIC_CHANGE,
        Permission.EXECUTE_ROLLBACK,
        Permission.EXECUTE_GENERIC_EXECUTION,
        Permission.APPROVE_CHANGE,
        Permission.APPROVE_FINANCE_CHANGE,
        Permission.APPROVE_PRODUCTION_CHANGE,
        Permission.ACTIVATE_KILL_SWITCH,
        Permission.RELEASE_KILL_SWITCH,
        Permission.MANAGE_TENANT_POLICY,
    }),
    RoleId.OPERATOR: frozenset({
        Permission.VIEW_APPROVALS,
        Permission.VIEW_POLICY,
        Permission.EXECUTE_SAFE_READ,
        Permission.EXECUTE_INTERNAL_WRITE,
        Permission.EXECUTE_OUTBOUND,
        Permission.EXECUTE_PUBLICATION,
        Permission.EXECUTE_GENERIC_EXECUTION,
    }),
    RoleId.ANALYST: frozenset({
        Permission.VIEW_APPROVALS,
        Permission.VIEW_POLICY,
        Permission.EXECUTE_SAFE_READ,
    }),
    RoleId.FINANCE: frozenset({
        Permission.VIEW_AUDIT,
        Permission.VIEW_APPROVALS,
        Permission.VIEW_POLICY,
        Permission.EXECUTE_SAFE_READ,
        Permission.APPROVE_CHANGE,
        Permission.APPROVE_FINANCE_CHANGE,
    }),
    RoleId.AUDITOR: frozenset({
        Permission.VIEW_AUDIT,
        Permission.VIEW_APPROVALS,
        Permission.VIEW_POLICY,
    }),
    RoleId.SECURITY: frozenset({
        Permission.VIEW_AUDIT,
        Permission.VIEW_APPROVALS,
        Permission.VIEW_POLICY,
        Permission.APPROVE_CHANGE,
        Permission.APPROVE_PRODUCTION_CHANGE,
        Permission.ACTIVATE_KILL_SWITCH,
        Permission.RELEASE_KILL_SWITCH,
    }),
    RoleId.SUPPORT: frozenset({
        Permission.VIEW_POLICY,
        Permission.EXECUTE_SAFE_READ,
        Permission.EXECUTE_OUTBOUND,
    }),
    RoleId.VIEWER: frozenset({
        Permission.VIEW_POLICY,
    }),
}


_ACTION_CATEGORY_TO_PERMISSION: dict[str, Permission] = {
    ActionCategory.SAFE_READ.value: Permission.EXECUTE_SAFE_READ,
    ActionCategory.INTERNAL_WRITE.value: Permission.EXECUTE_INTERNAL_WRITE,
    ActionCategory.OUTBOUND.value: Permission.EXECUTE_OUTBOUND,
    ActionCategory.PUBLICATION.value: Permission.EXECUTE_PUBLICATION,
    ActionCategory.BUDGET_CHANGE.value: Permission.EXECUTE_BUDGET_CHANGE,
    ActionCategory.STRATEGIC_CHANGE.value: Permission.EXECUTE_STRATEGIC_CHANGE,
    ActionCategory.ROLLBACK.value: Permission.EXECUTE_ROLLBACK,
    ActionCategory.EXECUTION.value: Permission.EXECUTE_GENERIC_EXECUTION,
}


class PermissionMatrix(PermissionMatrixContract):
    def permissions_for_role(self, role_id: RoleId) -> frozenset[Permission]:
        return _ROLE_PERMISSIONS.get(role_id, frozenset())

    def permission_for_action_category(self, category: str) -> Permission | None:
        return _ACTION_CATEGORY_TO_PERMISSION.get(str(category or "").strip())


def permissions_for_roles(role_ids: frozenset[RoleId]) -> frozenset[Permission]:
    merged: set[Permission] = set()
    for role_id in role_ids:
        merged.update(_ROLE_PERMISSIONS.get(role_id, ()))
    return frozenset(merged)


__all__ = [
    "CANON_GOVERNANCE_PERMISSION_MATRIX",
    "PermissionMatrix",
    "permissions_for_roles",
]

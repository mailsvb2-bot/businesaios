from __future__ import annotations

from governance.permission_matrix import permissions_for_roles
from governance.rbac_contract import (
    AccessRequest,
    AccessVerdict,
    Permission,
    PermissionMatrixContract,
    RoleCatalogContract,
)
from governance.tenant_policy_overrides import TenantPolicyOverrideRegistry


CANON_GOVERNANCE_RBAC_POLICY = True


class RbacPolicy:
    def __init__(
        self,
        *,
        role_catalog: RoleCatalogContract,
        permission_matrix: PermissionMatrixContract,
        tenant_overrides: TenantPolicyOverrideRegistry | None = None,
    ) -> None:
        self._role_catalog = role_catalog
        self._permission_matrix = permission_matrix
        self._tenant_overrides = tenant_overrides or TenantPolicyOverrideRegistry()

    def evaluate(self, request: AccessRequest) -> AccessVerdict:
        request.validate()

        normalized_roles = self._role_catalog.normalize_roles(request.actor.role_ids)
        if not normalized_roles:
            return AccessVerdict(
                allowed=False,
                reason="no_known_roles",
                matched_roles=(),
                effective_permissions=frozenset(),
                operator_required=True,
                audit_fields={"permission": request.permission.value},
            )

        effective_permissions = self._tenant_overrides.effective_permissions(
            tenant_id=request.actor.tenant_id,
            base_permissions=permissions_for_roles(normalized_roles),
        )

        action_name = str(request.action_name or "")
        action_category = str(request.metadata.get("action_category") or "")

        if self._tenant_overrides.is_action_blocked(
            tenant_id=request.actor.tenant_id,
            action_name=action_name,
            category=action_category,
        ):
            return AccessVerdict(
                allowed=False,
                reason="blocked_by_tenant_policy_override",
                matched_roles=tuple(sorted(normalized_roles, key=lambda x: x.value)),
                effective_permissions=effective_permissions,
                operator_required=True,
                audit_fields={
                    "permission": request.permission.value,
                    "action_name": action_name,
                    "action_category": action_category,
                },
            )

        if request.permission not in effective_permissions:
            return AccessVerdict(
                allowed=False,
                reason="missing_permission",
                matched_roles=tuple(sorted(normalized_roles, key=lambda x: x.value)),
                effective_permissions=effective_permissions,
                operator_required=True,
                audit_fields={
                    "permission": request.permission.value,
                    "action_name": action_name,
                    "action_category": action_category,
                },
            )

        return AccessVerdict(
            allowed=True,
            reason="allowed",
            matched_roles=tuple(sorted(normalized_roles, key=lambda x: x.value)),
            effective_permissions=effective_permissions,
            operator_required=False,
            audit_fields={
                "permission": request.permission.value,
                "action_name": action_name,
                "action_category": action_category,
            },
        )

    def require_allowed(self, request: AccessRequest) -> None:
        verdict = self.evaluate(request)
        if not verdict.allowed:
            raise PermissionError(verdict.reason)

    def required_permission_for_action_category(self, category: str) -> Permission | None:
        return self._permission_matrix.permission_for_action_category(category)


__all__ = [
    "CANON_GOVERNANCE_RBAC_POLICY",
    "RbacPolicy",
]

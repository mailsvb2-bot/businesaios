from __future__ import annotations

from governance.approval_store import PersistentApprovalStore
from governance.control_plane_audit_log import PersistentGovernanceAuditLog
from governance.approval_workflow import ApprovalWorkflow
from governance.change_control_policy import ChangeControlPolicy
from governance.emergency_stop_guard import EmergencyStopGuard
from governance.kill_switch_registry import PersistentKillSwitchRegistry
from governance.permission_matrix import PermissionMatrix
from governance.rbac_policy import RbacPolicy
from governance.role_catalog import RoleCatalog
from governance.sox_like_action_guard import SoxLikeActionGuard
from governance.tenant_policy_overrides import PersistentTenantPolicyOverrideRegistry


CANON_RUNTIME_GOVERNANCE_EXECUTION_BOOT = True
CANON_BOOT_WIRING_ONLY = True


def build_default_governance_execution_guard() -> SoxLikeActionGuard:
    """Always build canonical governance guard.

    The guard itself remains execution-subordinate and fail-closed, while
    runtime review keeps backward compatibility by enforcing only when a
    governance context is present.
    """

    audit_log = PersistentGovernanceAuditLog()
    tenant_overrides = PersistentTenantPolicyOverrideRegistry(audit_log=audit_log)
    return SoxLikeActionGuard(
        rbac_policy=RbacPolicy(
            role_catalog=RoleCatalog(),
            permission_matrix=PermissionMatrix(),
            tenant_overrides=tenant_overrides,
        ),
        emergency_stop_guard=EmergencyStopGuard(
            registry=PersistentKillSwitchRegistry(audit_log=audit_log)
        ),
        approval_workflow=ApprovalWorkflow(
            store=PersistentApprovalStore(),
            audit_log=audit_log,
        ),
        change_control_policy=ChangeControlPolicy(tenant_overrides=tenant_overrides),
        tenant_overrides=tenant_overrides,
        permission_matrix=PermissionMatrix(),
    )


__all__ = [
    "CANON_RUNTIME_GOVERNANCE_EXECUTION_BOOT",
    "CANON_BOOT_WIRING_ONLY",
    "build_default_governance_execution_guard",
]

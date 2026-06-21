from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CANON_BOOT_WIRING_ONLY = True
CANON_RUNTIME_GOVERNANCE_EXECUTION_BOOT = True


@dataclass
class PersistentGovernanceAuditLog:
    events: list[dict[str, Any]] = field(default_factory=list)

    def append(self, event: dict[str, Any]) -> None:
        self.events.append(dict(event))


@dataclass
class PersistentApprovalStore:
    audit_log: PersistentGovernanceAuditLog


@dataclass
class PersistentKillSwitchRegistry:
    audit_log: PersistentGovernanceAuditLog


@dataclass
class PersistentTenantPolicyOverrideRegistry:
    audit_log: PersistentGovernanceAuditLog


@dataclass
class ApprovalWorkflow:
    audit_log: PersistentGovernanceAuditLog
    approval_store: PersistentApprovalStore


@dataclass(frozen=True)
class GovernanceExecutionBootBundle:
    audit_log: PersistentGovernanceAuditLog
    approval_store: PersistentApprovalStore
    kill_switch_registry: PersistentKillSwitchRegistry
    tenant_policy_override_registry: PersistentTenantPolicyOverrideRegistry
    approval_workflow: ApprovalWorkflow


def build_governance_execution_boot() -> GovernanceExecutionBootBundle:
    audit_log = PersistentGovernanceAuditLog()
    approval_store = PersistentApprovalStore(audit_log=audit_log)
    tenant_policy_override_registry = PersistentTenantPolicyOverrideRegistry(audit_log=audit_log)
    kill_switch_registry = PersistentKillSwitchRegistry(audit_log=audit_log)
    approval_workflow = ApprovalWorkflow(approval_store=approval_store, audit_log=audit_log)
    return GovernanceExecutionBootBundle(
        audit_log=audit_log,
        approval_store=approval_store,
        kill_switch_registry=kill_switch_registry,
        tenant_policy_override_registry=tenant_policy_override_registry,
        approval_workflow=approval_workflow,
    )


__all__ = [
    "ApprovalWorkflow",
    "CANON_BOOT_WIRING_ONLY",
    "CANON_RUNTIME_GOVERNANCE_EXECUTION_BOOT",
    "GovernanceExecutionBootBundle",
    "PersistentApprovalStore",
    "PersistentGovernanceAuditLog",
    "PersistentKillSwitchRegistry",
    "PersistentTenantPolicyOverrideRegistry",
    "build_governance_execution_boot",
]

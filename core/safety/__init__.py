"""Safety primitives and shared safety-control profile.

This package intentionally provides only gating/guardrail infrastructure.
It must never become a second decision center.
"""

from .kill_switch import KillSwitch, KillSwitchState
from .blast_radius import BlastRadiusPolicy, allow_action
from .operational import (
    ActionClassifier,
    ActionCostModel,
    ActionImpactBuilder,
    ActionOperationalSpec,
    BudgetAccountingEnvelope,
    ClassifiedAction,
    InMemoryOperationalBudgetLedger,
    OperationalActionRegistry,
    OperationalBudgetAccountant,
    OperationalBudgetCounters,
    OperationalBudgetDecision,
    OperationalBudgetGuard,
    OperationalBudgetPolicy,
    OperationalBudgetService,
    OperationalSafetyRuntime,
    PersistentOperationalBudgetLedger,
    PrecheckResult,
    TenantOperationalBudgetPolicyProvider,
    build_default_operational_action_registry,
    build_operational_safety_runtime,
    build_operational_safety_runtime_with_components,
    build_persistent_operational_safety_runtime,
)

__all__ = [
    "KillSwitch",
    "KillSwitchState",
    "BlastRadiusPolicy",
    "allow_action",
    "ActionClassifier",
    "ActionCostModel",
    "ActionImpactBuilder",
    "ActionOperationalSpec",
    "BudgetAccountingEnvelope",
    "ClassifiedAction",
    "InMemoryOperationalBudgetLedger",
    "OperationalActionRegistry",
    "OperationalBudgetAccountant",
    "OperationalBudgetCounters",
    "OperationalBudgetDecision",
    "OperationalBudgetGuard",
    "OperationalBudgetPolicy",
    "OperationalBudgetService",
    "OperationalSafetyRuntime",
    "PersistentOperationalBudgetLedger",
    "PrecheckResult",
    "TenantOperationalBudgetPolicyProvider",
    "build_default_operational_action_registry",
    "build_operational_safety_runtime",
    "build_operational_safety_runtime_with_components",
    "build_persistent_operational_safety_runtime",
]

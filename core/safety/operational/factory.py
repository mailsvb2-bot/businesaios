from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.safety.operational.action_classifier import ActionClassifier
from core.safety.operational.action_cost_model import ActionCostModel
from core.safety.operational.action_impact_builder import ActionImpactBuilder
from core.safety.operational.action_registry import build_default_operational_action_registry
from core.safety.operational.operational_budget_accountant import OperationalBudgetAccountant
from core.safety.operational.operational_budget_guard import OperationalBudgetGuard
from core.safety.operational.operational_budget_ledger import InMemoryOperationalBudgetLedger
from core.safety.operational.operational_budget_policy import OperationalBudgetPolicy
from core.safety.operational.operational_budget_service import OperationalBudgetService
from core.safety.operational.persistent_operational_budget_ledger import (
    PersistentOperationalBudgetLedger,
)
from core.safety.operational.ports import OperationalBudgetLedgerPort
from core.safety.operational.tenant_policy_provider import TenantOperationalBudgetPolicyProvider

CANON_OPERATIONAL_FACTORY = True


@dataclass(frozen=True)
class OperationalSafetyRuntime:
    service: OperationalBudgetService
    ledger: OperationalBudgetLedgerPort
    policy_provider: TenantOperationalBudgetPolicyProvider


def build_operational_safety_runtime() -> OperationalSafetyRuntime:
    default_policy = OperationalBudgetPolicy()
    return build_operational_safety_runtime_with_components(
        ledger=InMemoryOperationalBudgetLedger(),
        policy_provider=TenantOperationalBudgetPolicyProvider(default_policy=default_policy),
    )


def build_persistent_operational_safety_runtime(
    *,
    storage_path: str | Path,
    policy_provider: TenantOperationalBudgetPolicyProvider | None = None,
) -> OperationalSafetyRuntime:
    default_policy_provider = policy_provider or TenantOperationalBudgetPolicyProvider(
        default_policy=OperationalBudgetPolicy()
    )
    return build_operational_safety_runtime_with_components(
        ledger=PersistentOperationalBudgetLedger(storage_path=storage_path),
        policy_provider=default_policy_provider,
    )


def build_operational_safety_runtime_with_components(
    *,
    ledger: OperationalBudgetLedgerPort,
    policy_provider: TenantOperationalBudgetPolicyProvider,
) -> OperationalSafetyRuntime:
    registry = build_default_operational_action_registry()
    cost_model = ActionCostModel()
    classifier = ActionClassifier(registry)
    impact_builder = ActionImpactBuilder(classifier=classifier, cost_model=cost_model)
    accountant = OperationalBudgetAccountant()
    guard = OperationalBudgetGuard(
        ledger=ledger,
        policy_provider=policy_provider,
    )
    service = OperationalBudgetService(
        impact_builder=impact_builder,
        accountant=accountant,
        guard=guard,
        ledger=ledger,
    )
    return OperationalSafetyRuntime(
        service=service,
        ledger=ledger,
        policy_provider=policy_provider,
    )


__all__ = [
    "OperationalSafetyRuntime",
    "build_operational_safety_runtime",
    "build_operational_safety_runtime_with_components",
    "build_persistent_operational_safety_runtime",
]
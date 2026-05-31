"""Academic target architecture for BusinesAIOS.

This module is intentionally small and normative. It describes the final target
shape of the system without pretending the migration is already complete.
Legacy namespace maps may continue to exist during migration, but they must not
contradict the target model declared here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

ACADEMIC_TARGET_ARCHITECTURE_VERSION: Final[str] = "1.0"

CANONICAL_LAYER_STACK: Final[tuple[str, ...]] = (
    "kernel",
    "domain",
    "application",
    "ports",
    "adapters",
    "entrypoints",
    "bootstrap",
    "observability",
    "governance",
    "security",
    "config",
)

CANONICAL_EXECUTION_PATH: Final[tuple[str, ...]] = (
    "RequestOrGoal",
    "RequestModel",
    "WorldState",
    "DecisionCore",
    "ExecutionPlan",
    "EffectExecution",
    "Verification",
    "Evidence",
    "MemoryOrStateUpdate",
)

CURRENT_RUNTIME_ENFORCEMENT_SLICE: Final[tuple[str, ...]] = (
    "DecisionCore",
    "GovernanceChain",
    "ActionExecutor",
)

FORBIDDEN_DEPENDENCY_EDGES: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        ("kernel", "runtime"),
        ("kernel", "adapters"),
        ("domain", "runtime"),
        ("domain", "adapters"),
        ("domain", "entrypoints"),
        ("application", "boot"),
        ("application", "interfaces"),
        ("application", "concrete_adapter_impl"),
        ("entrypoints", "business_logic"),
        ("recovery", "new_decision_issuance"),
        ("learning", "hidden_decision_issuance"),
    }
)

TRANSITION_NAMESPACE_TARGETS: Final[dict[str, tuple[str, ...]]] = {
    "boot": ("bootstrap",),
    "runtime": ("application", "adapters", "entrypoints", "bootstrap", "observability", "security"),
    "core": ("kernel", "domain", "application", "ports", "observability", "governance", "security"),
    "interfaces": ("entrypoints", "adapters"),
    "interfaces.api": ("entrypoints.api", "adapters.api.fastapi"),
    "headless": ("application.headless", "entrypoints"),
    "infra": ("adapters",),
    "infrastructure": ("adapters",),
}

ACADEMIC_SINGLE_POLICY_SOURCE_RULE: Final[str] = (
    "Business thresholds, weights, limits, caps, confidence mappings, approval "
    "rules, and autonomy tiers must live only in config/ or in explicit "
    "domain/policies owners."
)


@dataclass(frozen=True)
class AcademicTargetArchitecture:
    version: str = ACADEMIC_TARGET_ARCHITECTURE_VERSION
    layer_stack: tuple[str, ...] = CANONICAL_LAYER_STACK
    execution_path: tuple[str, ...] = CANONICAL_EXECUTION_PATH


TARGET_ARCHITECTURE: Final[AcademicTargetArchitecture] = AcademicTargetArchitecture()

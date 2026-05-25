from __future__ import annotations

"""Canonical runtime dependency set catalog.

This module is a boot catalog, not a runtime assembly path. It exists so
registration owners can declare dependencies without embedding dependency
knowledge in service constructors.
"""

from typing import Final

from runtime.service_names import RuntimeServiceName

CANON_RUNTIME_DEPENDENCY_SET_CATALOG_OWNER: Final[bool] = True

OBSERVABILITY_DEPS: Final[tuple[str, ...]] = ()
RISK_ENGINE_DEPS: Final[tuple[str, ...]] = ()
REWARD_GUARD_DEPS: Final[tuple[str, ...]] = ()
SIMULATION_GATE_DEPS: Final[tuple[str, ...]] = ()
KILL_SWITCH_DEPS: Final[tuple[str, ...]] = ()
ACTION_BUDGET_DEPS: Final[tuple[str, ...]] = ()
ACTION_EXECUTOR_DEPS: Final[tuple[str, ...]] = ()

GOVERNANCE_CHAIN_DEPS: Final[tuple[str, ...]] = (
    RuntimeServiceName.RISK_ENGINE,
    RuntimeServiceName.REWARD_GUARD,
    RuntimeServiceName.SIMULATION_GATE,
    RuntimeServiceName.KILL_SWITCH,
    RuntimeServiceName.ACTION_BUDGET,
)
DECISION_CORE_DEPS: Final[tuple[str, ...]] = (
    RuntimeServiceName.GOVERNANCE_CHAIN,
    RuntimeServiceName.ACTION_EXECUTOR,
)

RUNTIME_DEPENDENCY_SETS: Final[dict[str, tuple[str, ...]]] = {
    RuntimeServiceName.OBSERVABILITY: OBSERVABILITY_DEPS,
    RuntimeServiceName.RISK_ENGINE: RISK_ENGINE_DEPS,
    RuntimeServiceName.REWARD_GUARD: REWARD_GUARD_DEPS,
    RuntimeServiceName.SIMULATION_GATE: SIMULATION_GATE_DEPS,
    RuntimeServiceName.KILL_SWITCH: KILL_SWITCH_DEPS,
    RuntimeServiceName.ACTION_BUDGET: ACTION_BUDGET_DEPS,
    RuntimeServiceName.GOVERNANCE_CHAIN: GOVERNANCE_CHAIN_DEPS,
    RuntimeServiceName.ACTION_EXECUTOR: ACTION_EXECUTOR_DEPS,
    RuntimeServiceName.DECISION_CORE: DECISION_CORE_DEPS,
}


__all__ = [
    "ACTION_BUDGET_DEPS",
    "ACTION_EXECUTOR_DEPS",
    "CANON_RUNTIME_DEPENDENCY_SET_CATALOG_OWNER",
    "DECISION_CORE_DEPS",
    "GOVERNANCE_CHAIN_DEPS",
    "KILL_SWITCH_DEPS",
    "OBSERVABILITY_DEPS",
    "REWARD_GUARD_DEPS",
    "RISK_ENGINE_DEPS",
    "RUNTIME_DEPENDENCY_SETS",
    "SIMULATION_GATE_DEPS",
]

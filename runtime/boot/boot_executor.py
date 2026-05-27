from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True

"""Executor assembly helpers extracted from boot_core_assembly."""

from typing import Any

from bootstrap.decision_core_contract import RuntimeDecisionCorePort
from bootstrap.governance_execution_boot import build_default_governance_execution_guard
from governance.economic_layer import EconomicAutonomyLayer
from runtime.execution.executor_state import RuntimeExecutorInfra, build_executor_runtime_infra_from_runtime_infra
from runtime.executor import RuntimeExecutor
from runtime.guard import RuntimeGuard
from runtime.recovery import recover_pending
from runtime.safety import resolve_operational_safety_runtime


def build_runtime_infra(*, runtime_infra, delivery_state, telegram_outbound_queue, **_unused):
    return build_executor_runtime_infra_from_runtime_infra(
        runtime_infra=runtime_infra,
        delivery_state=delivery_state,
        telegram_outbound_queue=telegram_outbound_queue,
    )


def build_executor(*, guard: RuntimeGuard, handlers: Any, event_log: Any, policy_registry: Any, reward_engine: Any, learning: Any, core: RuntimeDecisionCorePort, decision_archive: Any, economic_layer: EconomicAutonomyLayer, runtime_infra: RuntimeExecutorInfra) -> RuntimeExecutor:
    operational_runtime = resolve_operational_safety_runtime(default_root='.runtime')
    executor = RuntimeExecutor(
        guard,
        handlers,
        event_log,
        policy_registry=policy_registry,
        reward_engine=reward_engine,
        learning_system=learning,
        decision_core=core,
        decision_archive=decision_archive,
        economic_layer=economic_layer,
        runtime_infra=runtime_infra,
        operational_budget_service=operational_runtime.service,
    )
    executor._governance_execution_guard = build_default_governance_execution_guard()
    recover_pending(executor=executor, outbox=runtime_infra.outbox, archive=decision_archive, limit=100)
    return executor


__all__ = ["CANON_BOOT_WIRING_ONLY", "build_runtime_infra", "build_executor"]

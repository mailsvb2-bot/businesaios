"""Canonical runtime application contract surface.

This module is the single owner for lightweight runtime-owned application
contracts derived from the runtime registry and decision-core access boundary.
Historical modules under ``runtime.application.*`` as well as legacy root-level
access helpers remain transition ABI only. This file is the single owner for
runtime application access/contracts surface and must not absorb business logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from application.decision.decision_service import DecisionApplicationService
from runtime.access_policies import validate_capability_access
from runtime.application._ports_impl import (
    DecisionExecutionPort,
    ObservabilityPort,
    build_decision_execution_port,
    build_nullable_observability_port,
)
from runtime.registry import RuntimeRegistry
from runtime.service_names import RuntimeServiceName

CANON_RUNTIME_APPLICATION_CONTRACTS = True
CANON_SINGLE_OWNER = True

class RuntimeDecisionCorePort(Protocol):
    decide: Any

    def issue(self, state: Any) -> Any: ...


@dataclass(frozen=True)
class ReadOnlyRuntimeRegistry:
    _registry: RuntimeRegistry

    def get(self, name: str) -> object:
        return self._registry.get(name)

    def has(self, name: str) -> bool:
        return self._registry.has(name)

    def service_type_of(self, name: str) -> str:
        return self._registry.service_type_of(name)

    def dependencies_of(self, name: str) -> tuple[str, ...]:
        return self._registry.dependencies_of(name)

    def list_service_names(self) -> tuple[str, ...]:
        return self._registry.list_service_names()

    def snapshot(self):
        return self._registry.snapshot()


@dataclass(frozen=True)
class RuntimeServiceExports:
    decision_execution: DecisionExecutionPort
    observability: ObservabilityPort


@dataclass(frozen=True)
class RuntimeTypedAccess:
    registry: RuntimeRegistry

    def observability(self) -> object:
        return self.registry.get(RuntimeServiceName.OBSERVABILITY)

    def risk_engine(self) -> object:
        return self.registry.get(RuntimeServiceName.RISK_ENGINE)

    def reward_guard(self) -> object:
        return self.registry.get(RuntimeServiceName.REWARD_GUARD)

    def simulation_gate(self) -> object:
        return self.registry.get(RuntimeServiceName.SIMULATION_GATE)

    def kill_switch(self) -> object:
        return self.registry.get(RuntimeServiceName.KILL_SWITCH)

    def action_budget(self) -> object:
        return self.registry.get(RuntimeServiceName.ACTION_BUDGET)

    def governance_chain(self) -> object:
        return self.registry.get(RuntimeServiceName.GOVERNANCE_CHAIN)

    def action_executor(self) -> object:
        return self.registry.get(RuntimeServiceName.ACTION_EXECUTOR)

    def decision_core(self) -> object:
        return self.registry.get(RuntimeServiceName.DECISION_CORE)


@dataclass(frozen=True)
class RuntimeCapabilityAccess:
    registry: ReadOnlyRuntimeRegistry
    capability: str

    def get(self, service_name: str) -> object:
        validate_capability_access(
            capability=self.capability,
            service_name=service_name,
        )
        return self.registry.get(service_name)

CANON_RUNTIME_APPLICATION_SINGLE_DECISION_PATH = True




def build_runtime_service_exports_from_raw(
    *,
    decision_core: object,
    observability: object | None = None,
) -> RuntimeServiceExports:
    return RuntimeServiceExports(
        decision_execution=build_decision_execution_port(decision_core=decision_core),
        observability=build_nullable_observability_port(observability=observability),
    )

def build_runtime_application_service_from_exports(
    exports: RuntimeServiceExports,
) -> DecisionApplicationService:
    return DecisionApplicationService(
        decision_execution_port=exports.decision_execution,
        observability_port=exports.observability,
    )


def build_runtime_application_service_from_raw(
    *,
    decision_core: object,
    observability: object | None = None,
) -> DecisionApplicationService:
    return build_runtime_application_service_from_exports(
        build_runtime_service_exports_from_raw(
            decision_core=decision_core,
            observability=observability,
        )
    )


def build_runtime_application_service(
    registry: ReadOnlyRuntimeRegistry,
) -> DecisionApplicationService:
    return build_runtime_application_service_from_exports(
        build_runtime_service_exports(registry)
    )


def build_runtime_service_exports(
    registry: ReadOnlyRuntimeRegistry,
) -> RuntimeServiceExports:
    return build_runtime_service_exports_from_raw(
        decision_core=registry.get(RuntimeServiceName.DECISION_CORE),
        observability=registry.get(RuntimeServiceName.OBSERVABILITY),
    )


__all__ = [
    'CANON_RUNTIME_APPLICATION_CONTRACTS',
    'CANON_SINGLE_OWNER',
    'CANON_RUNTIME_APPLICATION_SINGLE_DECISION_PATH',
    'DecisionExecutionPort',
    'ObservabilityPort',
    'ReadOnlyRuntimeRegistry',
    'RuntimeCapabilityAccess',
    'RuntimeDecisionCorePort',
    'RuntimeServiceExports',
    'RuntimeTypedAccess',
    'build_runtime_application_service',
    'build_runtime_service_exports_from_raw',
    'build_runtime_application_service_from_exports',
    'build_runtime_application_service_from_raw',
    'build_runtime_service_exports',
]

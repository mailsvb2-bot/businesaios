"""Canonical runtime application contract surface.

This module is the single owner for lightweight runtime-owned application
contracts derived from the runtime registry. Runtime application code receives
an already-issued DecisionEnvelope and can only delegate it to the registered
execution service; it never resolves or invokes the sovereign DecisionCore.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

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
CANON_RUNTIME_APPLICATION_SINGLE_DECISION_PATH = True
CANON_RUNTIME_APPLICATION_EXECUTION_ONLY = True


class RuntimeDecisionExecutionPort(Protocol):
    def execute(self, envelope: object) -> object: ...


# Historical exported name. It now denotes the execution-only protocol and does
# not grant issue/decide authority.
RuntimeDecisionCorePort = RuntimeDecisionExecutionPort


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

    def decision_execution(self) -> object:
        return self.registry.get(
            RuntimeServiceName.RUNTIME_DECISION_EXECUTION_SERVICE
        )

    def decision_core(self) -> object:
        """Historical lookup alias for the execution service only."""

        return self.decision_execution()


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


def build_runtime_service_exports_from_raw(
    *,
    decision_core: object,
    observability: object | None = None,
) -> RuntimeServiceExports:
    """Compatibility builder around an execution-only owner.

    The ``decision_core`` keyword is retained for callers compiled against the
    historical API. Passing a sovereign issuer fails closed because the port
    rejects issue/decide/optimize surfaces and requires ``execute(envelope)``.
    """

    return RuntimeServiceExports(
        decision_execution=build_decision_execution_port(
            decision_core=decision_core
        ),
        observability=build_nullable_observability_port(
            observability=observability
        ),
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
        decision_core=registry.get(
            RuntimeServiceName.RUNTIME_DECISION_EXECUTION_SERVICE
        ),
        observability=registry.get(RuntimeServiceName.OBSERVABILITY),
    )


__all__ = [
    "CANON_RUNTIME_APPLICATION_CONTRACTS",
    "CANON_RUNTIME_APPLICATION_EXECUTION_ONLY",
    "CANON_RUNTIME_APPLICATION_SINGLE_DECISION_PATH",
    "CANON_SINGLE_OWNER",
    "DecisionExecutionPort",
    "ObservabilityPort",
    "ReadOnlyRuntimeRegistry",
    "RuntimeCapabilityAccess",
    "RuntimeDecisionCorePort",
    "RuntimeDecisionExecutionPort",
    "RuntimeServiceExports",
    "RuntimeTypedAccess",
    "build_runtime_application_service",
    "build_runtime_application_service_from_exports",
    "build_runtime_application_service_from_raw",
    "build_runtime_service_exports",
    "build_runtime_service_exports_from_raw",
]

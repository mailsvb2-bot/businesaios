from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Iterable

from deployment.health_contract import (
    HealthCheckResult,
    HealthCheckStatus,
    HealthExceptionPolicy,
    HealthReport,
    HealthSignal,
    ReadinessSnapshot,
)

if TYPE_CHECKING:
    from runtime.runtime_orchestrator import RuntimeOrchestrator


CANON_DEPLOYMENT_READINESS_CHECKS = True

DEFAULT_REQUIRED_SERVICES = ("event_bus", "metrics", "tracer")
DEFAULT_REQUIRED_COMPONENTS = ("decision_audit_log", "action_audit_log")


@dataclass(frozen=True)
class ReadinessDependencies:
    required_services: tuple[str, ...] = field(default_factory=lambda: DEFAULT_REQUIRED_SERVICES)
    required_components: tuple[str, ...] = field(default_factory=lambda: DEFAULT_REQUIRED_COMPONENTS)

    def __post_init__(self) -> None:
        if len(set(self.required_services)) != len(self.required_services):
            raise ValueError("required_services must be unique")
        if len(set(self.required_components)) != len(self.required_components):
            raise ValueError("required_components must be unique")


@dataclass(frozen=True)
class _NamedCheck:
    name: str
    run: Callable[[], HealthCheckResult]


def _registry_names(registry: object) -> tuple[str, ...]:
    keys = getattr(registry, "keys", None)
    if callable(keys):
        return tuple(sorted(str(name) for name in keys()))
    if isinstance(registry, dict):
        return tuple(sorted(str(name) for name in registry.keys()))
    names = getattr(registry, "names", None)
    if callable(names):
        return tuple(sorted(str(name) for name in names()))
    if isinstance(registry, (list, tuple, set, frozenset)):
        return tuple(sorted(str(name) for name in registry))
    return tuple()


def snapshot_runtime_readiness(
    orchestrator: RuntimeOrchestrator,
    *,
    dependencies: ReadinessDependencies | None = None,
) -> ReadinessSnapshot:
    deps = dependencies or ReadinessDependencies()
    services = _registry_names(orchestrator.services)
    components = _registry_names(orchestrator.components)
    state = orchestrator.state
    gate_ready = bool(orchestrator.readiness.is_ready(state))
    missing_services = tuple(name for name in deps.required_services if name not in services)
    missing_components = tuple(name for name in deps.required_components if name not in components)
    return ReadinessSnapshot(
        service_names=services,
        component_names=components,
        runtime_booted=bool(state.booted),
        runtime_state_ready=bool(state.ready),
        readiness_gate_ready=gate_ready,
        shutting_down=bool(state.shutting_down),
        missing_services=missing_services,
        missing_components=missing_components,
    )


class ReadinessCheckRegistry:
    def __init__(
        self,
        *,
        exception_policy: HealthExceptionPolicy = HealthExceptionPolicy.FAIL_CLOSED,
    ) -> None:
        self._checks: list[_NamedCheck] = []
        self._exception_policy = exception_policy

    def register(self, name: str, check: Callable[[], HealthCheckResult]) -> None:
        normalized = str(name or "").strip()
        if not normalized:
            raise ValueError("readiness check name is required")
        if any(item.name == normalized for item in self._checks):
            raise ValueError(f"duplicate readiness check: {normalized}")
        self._checks.append(_NamedCheck(name=normalized, run=check))

    def extend(self, checks: Iterable[tuple[str, Callable[[], HealthCheckResult]]]) -> None:
        for name, check in checks:
            self.register(name, check)

    def _run_single(self, item: _NamedCheck) -> HealthCheckResult:
        try:
            result = item.run()
        except Exception as exc:
            status = (
                HealthCheckStatus.FAIL
                if self._exception_policy is HealthExceptionPolicy.FAIL_CLOSED
                else HealthCheckStatus.WARN
            )
            return HealthCheckResult(
                name=item.name,
                status=status,
                signal=HealthSignal.READINESS,
                summary=f"check raised exception: {item.name}",
                details={"error_type": type(exc).__name__, "error": str(exc)},
            )
        if result.name != item.name:
            return HealthCheckResult(
                name=item.name,
                status=HealthCheckStatus.FAIL,
                signal=result.signal,
                summary="check returned mismatched result name",
                details={"expected": item.name, "actual": result.name},
            )
        return result

    def run_all(
        self,
        *,
        service: str,
        version: str | None = None,
        release_id: str | None = None,
    ) -> HealthReport:
        if not self._checks:
            raise ValueError("readiness registry must contain at least one check")
        results = tuple(self._run_single(item) for item in self._checks)
        return HealthReport.aggregate(
            service=service,
            checks=results,
            version=version,
            release_id=release_id,
        )

    def names(self) -> tuple[str, ...]:
        return tuple(item.name for item in self._checks)


def _runtime_state_check(
    orchestrator: RuntimeOrchestrator,
    *,
    dependencies: ReadinessDependencies,
) -> HealthCheckResult:
    snapshot = snapshot_runtime_readiness(orchestrator, dependencies=dependencies)
    details = snapshot.to_dict()
    if snapshot.ready:
        return HealthCheckResult(
            name="runtime_state",
            status=HealthCheckStatus.PASS,
            signal=HealthSignal.READINESS,
            summary="runtime state is ready",
            details=details,
        )
    summary_parts: list[str] = []
    if not snapshot.runtime_booted:
        summary_parts.append("runtime not booted")
    if not snapshot.runtime_state_ready:
        summary_parts.append("runtime state.ready is false")
    if not snapshot.readiness_gate_ready:
        summary_parts.append("readiness gate is false")
    if snapshot.shutting_down:
        summary_parts.append("runtime is shutting down")
    if snapshot.missing_services:
        summary_parts.append(f"missing services={','.join(snapshot.missing_services)}")
    if snapshot.missing_components:
        summary_parts.append(f"missing components={','.join(snapshot.missing_components)}")
    return HealthCheckResult(
        name="runtime_state",
        status=HealthCheckStatus.FAIL,
        signal=HealthSignal.READINESS,
        summary="; ".join(summary_parts) or "runtime readiness failed",
        details=details,
    )


def _registry_presence_check(
    orchestrator: RuntimeOrchestrator,
    *,
    dependencies: ReadinessDependencies,
) -> HealthCheckResult:
    snapshot = snapshot_runtime_readiness(orchestrator, dependencies=dependencies)
    if snapshot.service_count == 0 or snapshot.component_count == 0:
        return HealthCheckResult(
            name="registry_presence",
            status=HealthCheckStatus.FAIL,
            signal=HealthSignal.DEPENDENCY,
            summary="runtime registries are empty",
            details=snapshot.to_dict(),
        )
    return HealthCheckResult(
        name="registry_presence",
        status=HealthCheckStatus.PASS,
        signal=HealthSignal.DEPENDENCY,
        summary="runtime registries are present",
        details={
            "service_count": snapshot.service_count,
            "component_count": snapshot.component_count,
        },
    )


def _observability_wiring_check(
    orchestrator: RuntimeOrchestrator,
    *,
    dependencies: ReadinessDependencies,
) -> HealthCheckResult:
    snapshot = snapshot_runtime_readiness(orchestrator, dependencies=dependencies)
    if snapshot.missing_services or snapshot.missing_components:
        return HealthCheckResult(
            name="observability_wiring",
            status=HealthCheckStatus.FAIL,
            signal=HealthSignal.OBSERVABILITY,
            summary="required operational surfaces are missing",
            details={
                "missing_services": snapshot.missing_services,
                "missing_components": snapshot.missing_components,
            },
        )
    return HealthCheckResult(
        name="observability_wiring",
        status=HealthCheckStatus.PASS,
        signal=HealthSignal.OBSERVABILITY,
        summary="required operational surfaces are wired",
        details={
            "required_services": dependencies.required_services,
            "required_components": dependencies.required_components,
        },
    )


def _readiness_consistency_check(
    orchestrator: RuntimeOrchestrator,
    *,
    dependencies: ReadinessDependencies,
) -> HealthCheckResult:
    snapshot = snapshot_runtime_readiness(orchestrator, dependencies=dependencies)
    inconsistent = snapshot.runtime_state_ready != snapshot.readiness_gate_ready
    if inconsistent:
        return HealthCheckResult(
            name="readiness_consistency",
            status=HealthCheckStatus.FAIL,
            signal=HealthSignal.READINESS,
            summary="runtime state and readiness gate disagree",
            details={
                "runtime_state_ready": snapshot.runtime_state_ready,
                "readiness_gate_ready": snapshot.readiness_gate_ready,
            },
        )
    return HealthCheckResult(
        name="readiness_consistency",
        status=HealthCheckStatus.PASS,
        signal=HealthSignal.READINESS,
        summary="runtime state and readiness gate agree",
        details={
            "runtime_state_ready": snapshot.runtime_state_ready,
            "readiness_gate_ready": snapshot.readiness_gate_ready,
        },
    )


def build_default_readiness_registry(
    orchestrator: RuntimeOrchestrator,
    *,
    dependencies: ReadinessDependencies | None = None,
    exception_policy: HealthExceptionPolicy = HealthExceptionPolicy.FAIL_CLOSED,
) -> ReadinessCheckRegistry:
    deps = dependencies or ReadinessDependencies()
    registry = ReadinessCheckRegistry(exception_policy=exception_policy)
    registry.extend(
        (
            ("runtime_state", lambda: _runtime_state_check(orchestrator, dependencies=deps)),
            ("registry_presence", lambda: _registry_presence_check(orchestrator, dependencies=deps)),
            ("observability_wiring", lambda: _observability_wiring_check(orchestrator, dependencies=deps)),
            ("readiness_consistency", lambda: _readiness_consistency_check(orchestrator, dependencies=deps)),
        )
    )
    return registry


__all__ = [
    "CANON_DEPLOYMENT_READINESS_CHECKS",
    "DEFAULT_REQUIRED_COMPONENTS",
    "DEFAULT_REQUIRED_SERVICES",
    "ReadinessCheckRegistry",
    "ReadinessDependencies",
    "build_default_readiness_registry",
    "snapshot_runtime_readiness",
]

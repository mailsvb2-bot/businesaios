"""Global managed-runtime plane.

Operational only. This module owns lifecycle registration/start/stop/join ordering
for already-built managed runtimes. It must not introduce business policy,
planning, provider ranking, or any alternate decision path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from runtime.runtime_observability import RuntimeObservability

CANON_MANAGED_RUNTIME_PLANE = True
CANON_MANAGED_RUNTIME_PLANE_NO_DECISION_LOGIC = True

@dataclass(frozen=True)
class ManagedRuntimeRecord:
    name: str
    owner_service: str
    runtime_type: str
    dependencies: tuple[str, ...] = ()
    started: bool = False


@dataclass
class ManagedRuntimePlane:
    observability: RuntimeObservability | None = None
    _records: dict[str, ManagedRuntimeRecord] = field(default_factory=dict)
    _runtimes: dict[str, Any] = field(default_factory=dict)

    def register_runtime(
        self,
        *,
        name: str,
        runtime: Any,
        owner_service: str,
        dependencies: tuple[str, ...] = (),
    ) -> ManagedRuntimeRecord:
        runtime_name = str(name).strip()
        owner = str(owner_service).strip()
        if not runtime_name:
            raise ValueError('runtime name is required')
        if not owner:
            raise ValueError('owner_service is required')
        self._validate_runtime_surface(runtime)
        dep_tuple = tuple(str(item).strip() for item in dependencies if str(item).strip())
        self._runtimes[runtime_name] = runtime
        record = ManagedRuntimeRecord(
            name=runtime_name,
            owner_service=owner,
            runtime_type=type(runtime).__name__,
            dependencies=dep_tuple,
            started=False,
        )
        self._records[runtime_name] = record
        self._record_audit_event(
            'managed_runtime_registered',
            runtime_name=runtime_name,
            owner_service=owner,
            runtime_type=type(runtime).__name__,
        )
        return record

    def has_runtime(self, name: str) -> bool:
        return str(name).strip() in self._records

    def runtime(self, name: str) -> Any:
        runtime_name = str(name).strip()
        if runtime_name not in self._runtimes:
            raise KeyError(f'managed runtime not registered: {runtime_name}')
        return self._runtimes[runtime_name]

    def start_runtime(self, name: str) -> None:
        runtime_name = str(name).strip()
        for dependency in self._records.get(runtime_name, ManagedRuntimeRecord('', '', '')).dependencies:
            if dependency not in self._records:
                raise KeyError(f'missing managed-runtime dependency: {dependency}')
            if not self._records[dependency].started:
                self.start_runtime(dependency)
        runtime = self.runtime(runtime_name)
        runtime.start()
        record = self._records[runtime_name]
        self._records[runtime_name] = ManagedRuntimeRecord(
            name=record.name,
            owner_service=record.owner_service,
            runtime_type=record.runtime_type,
            dependencies=record.dependencies,
            started=True,
        )
        self._record_audit_event('managed_runtime_started', runtime_name=runtime_name)

    def pulse_runtime_once(self, name: str) -> tuple[dict[str, Any], ...]:
        runtime_name = str(name).strip()
        results = tuple(self.runtime(runtime_name).pulse_once())
        self._record_audit_event('managed_runtime_pulsed', runtime_name=runtime_name, results_count=len(results))
        return results

    def request_runtime_stop(self, name: str, *, reason: str = 'managed_runtime_stop') -> None:
        runtime_name = str(name).strip()
        self.runtime(runtime_name).request_stop(reason=reason)
        self._record_audit_event('managed_runtime_stop_requested', runtime_name=runtime_name, reason=str(reason))

    def join_runtime(self, name: str, *, timeout_seconds: float = 10.0) -> Any:
        runtime_name = str(name).strip()
        report = self.runtime(runtime_name).join(timeout_seconds=timeout_seconds)
        self._record_audit_event(
            'managed_runtime_joined',
            runtime_name=runtime_name,
            pulses=int(getattr(report, 'pulses', 0)),
            executed_results=int(getattr(report, 'executed_results', 0)),
        )
        return report

    def start_all(self) -> tuple[str, ...]:
        started: list[str] = []
        for runtime_name in self._topological_order():
            if not self._records[runtime_name].started:
                self.start_runtime(runtime_name)
                started.append(runtime_name)
        return tuple(started)

    def request_stop_all(self, *, reason: str = 'managed_runtime_plane_stop') -> tuple[str, ...]:
        stopped: list[str] = []
        for runtime_name in reversed(self._topological_order()):
            self.request_runtime_stop(runtime_name, reason=reason)
            stopped.append(runtime_name)
        return tuple(stopped)

    def join_all(self, *, timeout_seconds: float = 10.0) -> dict[str, Any]:
        reports: dict[str, Any] = {}
        for runtime_name in reversed(self._topological_order()):
            reports[runtime_name] = self.join_runtime(runtime_name, timeout_seconds=timeout_seconds)
        return reports

    def snapshot(self) -> dict[str, Any]:
        return {
            'managed_runtimes': {
                name: {
                    'record': record.__dict__,
                    'runtime_snapshot': self._safe_snapshot(name),
                }
                for name, record in sorted(self._records.items())
            }
        }

    def _safe_snapshot(self, name: str) -> Any:
        runtime = self._runtimes.get(name)
        if runtime is None or not hasattr(runtime, 'snapshot'):
            return None
        return runtime.snapshot()

    def _topological_order(self) -> tuple[str, ...]:
        visited: set[str] = set()
        active: set[str] = set()
        ordered: list[str] = []

        def visit(name: str) -> None:
            if name in visited:
                return
            if name in active:
                raise ValueError(f'cycle in managed-runtime dependencies: {name}')
            active.add(name)
            record = self._records[name]
            for dependency in record.dependencies:
                if dependency not in self._records:
                    raise KeyError(f'missing managed-runtime dependency: {dependency}')
                visit(dependency)
            active.remove(name)
            visited.add(name)
            ordered.append(name)

        for name in sorted(self._records):
            visit(name)
        return tuple(ordered)

    def _record_audit_event(self, event_name: str, **fields: Any) -> None:
        if self.observability is None:
            return
        self.observability.record_audit_event(event_name, **dict(fields))

    def _validate_runtime_surface(self, runtime: Any) -> None:
        required = ('start', 'pulse_once', 'request_stop', 'join', 'snapshot')
        for attr in required:
            if not hasattr(runtime, attr):
                raise TypeError(f'managed runtime must expose {attr}()')


__all__ = [
    'CANON_MANAGED_RUNTIME_PLANE',
    'CANON_MANAGED_RUNTIME_PLANE_NO_DECISION_LOGIC',
    'ManagedRuntimePlane',
    'ManagedRuntimeRecord',
]

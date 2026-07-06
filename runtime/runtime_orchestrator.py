"""Runtime readiness orchestrator.

This root-level surface is intentionally narrow: it validates the already-built
runtime registry state and marks lifecycle readiness. It must not become an
alternative runtime assembly path or absorb decision logic.
"""

from __future__ import annotations

from runtime.lifecycle import Lifecycle
from runtime.readiness import Readiness
from runtime.runtime_state import RuntimeState
from shared.registry import ComponentRegistry, ServiceRegistry

CANON_RUNTIME_ROOT_READINESS_OWNER = True
CANON_RUNTIME_ROOT_NO_ASSEMBLY = True
CANON_RUNTIME_ROOT_NO_DECISION_LOGIC = True

_REQUIRED_SERVICES = frozenset({"event_bus", "metrics", "tracer"})
_REQUIRED_COMPONENTS = frozenset({"decision_audit_log", "action_audit_log"})


class RuntimeOrchestrator:
    def __init__(self, services: ServiceRegistry, components: ComponentRegistry, state: RuntimeState | None = None) -> None:
        self.services = services
        self.components = components
        self.state = state or RuntimeState()
        self.lifecycle = Lifecycle(self.state)
        self.readiness = Readiness()

    def _validate_non_empty(self) -> None:
        if len(self.services) == 0:
            raise RuntimeError("runtime failed: no services registered")
        if len(self.components) == 0:
            raise RuntimeError("runtime failed: no components registered")

    def _missing_required_services(self) -> list[str]:
        return sorted(name for name in _REQUIRED_SERVICES if name not in self.services)

    def _missing_required_components(self) -> list[str]:
        return sorted(name for name in _REQUIRED_COMPONENTS if name not in self.components)

    def _require_required_services(self) -> None:
        missing_services = self._missing_required_services()
        if missing_services:
            raise RuntimeError(f"runtime failed: missing services: {missing_services}")

    def _require_required_components(self) -> None:
        missing_components = self._missing_required_components()
        if missing_components:
            raise RuntimeError(f"runtime failed: missing components: {missing_components}")

    def _mark_runtime_ready(self) -> None:
        self.lifecycle.mark_booted()
        self.lifecycle.mark_ready()

    def _require_readiness(self) -> None:
        if not self.readiness.is_ready(self.state):
            raise RuntimeError("runtime failed readiness check")

    def boot(self) -> RuntimeState:
        self._validate_non_empty()
        self._require_required_services()
        self._require_required_components()
        self._mark_runtime_ready()
        self._require_readiness()
        return self.state


__all__ = [
    "CANON_RUNTIME_ROOT_NO_ASSEMBLY",
    "CANON_RUNTIME_ROOT_NO_DECISION_LOGIC",
    "CANON_RUNTIME_ROOT_READINESS_OWNER",
    "RuntimeOrchestrator",
]

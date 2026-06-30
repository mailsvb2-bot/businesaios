"""Canonical dependency wiring for sovereign runtime bootstrap."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from runtime.bootstrap.bootstrap_contract import BootstrapEnvironment
from runtime.bootstrap.bootstrap_lock import BootstrapLock
from runtime.bootstrap.runtime_builder import build_runtime

CANON_RUNTIME_BOOTSTRAP_DEPENDENCY_WIRING_EXPLICIT_EXPORTS_ONLY = True

class RuntimeBuilder(Protocol):
    def __call__(self) -> Any: ...
class ProcessBootstrap(Protocol):
    def __call__(self, *, acquire_singleton_lock: bool = True) -> None: ...
class StartupValidator(Protocol):
    def __call__(self, env: BootstrapEnvironment) -> None: ...
class LockFactory(Protocol):
    def __call__(self, env: BootstrapEnvironment) -> BootstrapLock: ...
@dataclass(frozen=True)
class BootstrapDependencies:
    runtime_builder: RuntimeBuilder
    process_bootstrap: ProcessBootstrap
    startup_validator: StartupValidator
    lock_factory: LockFactory
def build_bootstrap_dependencies(
    *,
    runtime_builder: RuntimeBuilder = build_runtime,
    process_bootstrap: ProcessBootstrap,
    startup_validator: StartupValidator,
    lock_factory: LockFactory,
) -> BootstrapDependencies:
    return BootstrapDependencies(
        runtime_builder=runtime_builder,
        process_bootstrap=process_bootstrap,
        startup_validator=startup_validator,
        lock_factory=lock_factory,
    )


__all__ = [
    "CANON_RUNTIME_BOOTSTRAP_DEPENDENCY_WIRING_EXPLICIT_EXPORTS_ONLY",
    "BootstrapDependencies",
    "LockFactory",
    "ProcessBootstrap",
    "RuntimeBuilder",
    "StartupValidator",
    "build_bootstrap_dependencies",
]

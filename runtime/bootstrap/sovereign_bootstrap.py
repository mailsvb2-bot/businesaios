"""Canonical sovereign runtime bootstrap owner."""

from __future__ import annotations

import inspect
import threading
from dataclasses import dataclass, field
from runtime.bootstrap.bootstrap_attestation import build_bootstrap_attestation
from runtime.bootstrap.bootstrap_attestation_store import persist_bootstrap_attestation
from runtime.bootstrap.bootstrap_audit_trail import (
    append_bootstrap_audit_event,
    build_bootstrap_audit_event,
)
from runtime.bootstrap.bootstrap_contract import (
    BootstrapAttestationPolicy,
    BootstrapFailureCode,
    BootstrapStatus,
    SovereignRuntime,
)
from runtime.bootstrap.bootstrap_lock import BootstrapLock
from runtime.bootstrap.dependency_wiring import build_bootstrap_dependencies
from runtime.bootstrap.environment_loader import load_bootstrap_environment
from runtime.bootstrap.runtime_composition_root import compose_runtime
from runtime.bootstrap.startup_validator import (
    validate_single_bootstrap_path,
    validate_startup_environment,
)

@dataclass
class _BootstrapState:
    runtime: SovereignRuntime | None = None
    lock: BootstrapLock | None = None
    status: BootstrapStatus = BootstrapStatus.CREATED
    last_error: str | None = None
    boot_attempts: int = 0
    warnings: list[str] = field(default_factory=list)
_STATE = _BootstrapState()
_STATE_LOCK = threading.RLock()
CANON_SOVEREIGN_BOOTSTRAP_DIRECT_PROCESS_OWNER_IMPORT = True
CANON_RUNTIME_BOOTSTRAP_SOVEREIGN_EXPLICIT_EXPORTS_ONLY = True
CANON_RUNTIME_BOOTSTRAP_SOVEREIGN_OWNER = "runtime.bootstrap.sovereign_bootstrap"


def _process_bootstrap_owner():
    from runtime.bootstrap.process_bootstrap import run_process_bootstrap

    return run_process_bootstrap


def _legacy_process_bootstrap(*, acquire_singleton_lock: bool = True) -> None:
    _process_bootstrap_owner()(acquire_singleton_lock=acquire_singleton_lock)
def _lock_factory(env) -> BootstrapLock:
    return BootstrapLock(env.runtime_dir / "sovereign_bootstrap.lock")
def _active_module_names() -> set[str]:
    names: set[str] = set()
    for frame_info in inspect.stack():
        module = inspect.getmodule(frame_info.frame)
        if module is not None and getattr(module, "__name__", None):
            names.add(str(module.__name__))
    return names
def bootstrap_runtime(*, project_root: str | None = None) -> SovereignRuntime:
    with _STATE_LOCK:
        if _STATE.runtime is not None:
            return _STATE.runtime
        _STATE.status = BootstrapStatus.STARTING
        _STATE.last_error = None
        _STATE.boot_attempts += 1
        env = load_bootstrap_environment(project_root=project_root)
        policy = BootstrapAttestationPolicy()
        deps = build_bootstrap_dependencies(
            process_bootstrap=_legacy_process_bootstrap,
            startup_validator=validate_startup_environment,
            lock_factory=_lock_factory,
        )
        lock = deps.lock_factory(env)
        try:
            deps.startup_validator(env)
            validate_single_bootstrap_path(
                loaded_modules=_active_module_names(),
                env=env,
            )
            if env.singleton_lock_enabled:
                lock.acquire()
            deps.process_bootstrap(acquire_singleton_lock=False)
            composition = compose_runtime(
                env=env,
                runtime_builder=deps.runtime_builder,
                policy=policy,
            )
            attestation = build_bootstrap_attestation(
                env=env,
                artifacts=composition.artifacts,
                policy=policy,
            )
            persist_bootstrap_attestation(env=env, attestation=attestation)
            runtime = SovereignRuntime(
                status=BootstrapStatus.READY,
                environment=env,
                artifacts=composition.artifacts,
                attestation=attestation,
            )
            append_bootstrap_audit_event(
                env=env,
                event=build_bootstrap_audit_event(
                    status=BootstrapStatus.READY,
                    code="BOOTSTRAP_READY",
                    message="sovereign runtime boot completed",
                    details={
                        "boot_id": attestation.boot_id,
                        "contract_version": attestation.policy.contract_version,
                    },
                ),
            )
            _STATE.lock = lock if env.singleton_lock_enabled else None
            _STATE.runtime = runtime
            _STATE.status = BootstrapStatus.READY
            _STATE.warnings = list(attestation.diagnostics.warnings)
            return runtime
        except Exception as exc:
            _STATE.status = BootstrapStatus.FAILED
            _STATE.last_error = str(exc)
            append_bootstrap_audit_event(
                env=env,
                event=build_bootstrap_audit_event(
                    status=BootstrapStatus.FAILED,
                    code="BOOTSTRAP_FAILED",
                    message=str(exc),
                    details={
                        "attempt": str(_STATE.boot_attempts),
                    },
                ),
            )
            if env.singleton_lock_enabled and lock.acquired:
                lock.release()
            raise
def get_bootstrapped_runtime() -> SovereignRuntime:
    runtime = _STATE.runtime
    if runtime is None:
        raise RuntimeError(BootstrapFailureCode.NOT_STARTED.value)
    return runtime


__all__ = [
    "CANON_RUNTIME_BOOTSTRAP_SOVEREIGN_EXPLICIT_EXPORTS_ONLY",
    "CANON_RUNTIME_BOOTSTRAP_SOVEREIGN_OWNER",
    "CANON_SOVEREIGN_BOOTSTRAP_DIRECT_PROCESS_OWNER_IMPORT",
    "bootstrap_runtime",
    "get_bootstrapped_runtime",
]

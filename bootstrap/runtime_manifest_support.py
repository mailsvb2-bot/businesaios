from __future__ import annotations

"""Final owner for runtime manifest support.

Physical ownership moved from `boot/*` to `bootstrap/*`.
Legacy boot surfaces remain thin compatibility shells."""

CANON_RUNTIME_MANIFEST_SUPPORT_FINAL_OWNER = True
CANON_RUNTIME_MANIFEST_SUPPORT_NO_RUNTIME_ASSEMBLY = True

"""Shared builders for runtime boot manifest entries.
This keeps the manifest declarative and reduces repetitive constructor wiring
without changing any service names, dependencies, or boot order.
"""
from runtime.manifest_entry import RuntimeManifestEntry
from runtime.service_types import RuntimeServiceType
def _entry(*, step_name: str, service_name: str, callable_name: str, service_type: str, dependencies: tuple[str, ...] = ()) -> RuntimeManifestEntry:
    module_path = f"boot.registrations.{callable_name}"
    return RuntimeManifestEntry(
        step_name=step_name,
        module_path=module_path,
        callable_name=callable_name,
        service_name=service_name,
        service_type=service_type,
        dependencies=dependencies,
    )
def guard_step(*, step_name: str, service_name: str, callable_name: str, dependencies: tuple[str, ...] = ()) -> RuntimeManifestEntry:
    return _entry(
        step_name=step_name,
        service_name=service_name,
        callable_name=callable_name,
        service_type=RuntimeServiceType.GUARD,
        dependencies=dependencies,
    )
def governance_step(*, step_name: str, service_name: str, callable_name: str, dependencies: tuple[str, ...] = ()) -> RuntimeManifestEntry:
    return _entry(
        step_name=step_name,
        service_name=service_name,
        callable_name=callable_name,
        service_type=RuntimeServiceType.GOVERNANCE,
        dependencies=dependencies,
    )
def executor_step(*, step_name: str, service_name: str, callable_name: str, dependencies: tuple[str, ...] = ()) -> RuntimeManifestEntry:
    return _entry(
        step_name=step_name,
        service_name=service_name,
        callable_name=callable_name,
        service_type=RuntimeServiceType.EXECUTOR,
        dependencies=dependencies,
    )
def core_step(*, step_name: str, service_name: str, callable_name: str, dependencies: tuple[str, ...] = ()) -> RuntimeManifestEntry:
    return _entry(
        step_name=step_name,
        service_name=service_name,
        callable_name=callable_name,
        service_type=RuntimeServiceType.CORE,
        dependencies=dependencies,
    )
__all__ = ["core_step", "executor_step", "governance_step", "guard_step"]

"""Canonical internal runtime builder.

This module owns runtime assembly for the sovereign bootstrap path. It is an
internal support surface, not a public entrypoint.
"""

from __future__ import annotations

from dataclasses import dataclass
from boot.runtime_boot_guard import validate_runtime_boot
from boot.runtime_boot_report import RuntimeBootReport
from boot.wiring.runtime_dependency_resolver import RuntimeDependencyResolver
from boot.wiring.runtime_manifest_loader import load_runtime_manifest
from boot.wiring.runtime_manifest_validator import validate_runtime_manifest
from boot.wiring.runtime_registration_invoker import RuntimeRegistrationInvoker
from runtime.application.contracts import (
    ReadOnlyRuntimeRegistry,
    RuntimeServiceExports,
    build_runtime_service_exports,
)
from runtime.boot_fingerprint import RuntimeBootFingerprint, build_boot_fingerprint
from runtime.registry import RuntimeRegistry
from runtime.service_names import RuntimeServiceName

CANON_RUNTIME_BUILDER_OWNER = True
CANON_RUNTIME_BUILDER_INTERNAL_ONLY = True
CANON_RUNTIME_BUILDER_NO_PUBLIC_ENTRYPOINT = True
CANON_RUNTIME_BOOTSTRAP_RUNTIME_BUILDER_EXPLICIT_EXPORTS_ONLY = True

@dataclass(frozen=True)
class BuiltRuntime:
    registry: RuntimeRegistry
    report: RuntimeBootReport
    exports: RuntimeServiceExports
    fingerprint: RuntimeBootFingerprint

    def __iter__(self):
        yield self.registry
        yield self.report


@dataclass
class RuntimeBuilder:
    resolver: RuntimeDependencyResolver

    def build_runtime(self) -> BuiltRuntime:
        registry = RuntimeRegistry()
        report = RuntimeBootReport()
        observability = None
        manifest = load_runtime_manifest()
        validate_runtime_manifest(manifest)
        registry.begin_registration()
        invoker = RuntimeRegistrationInvoker(self.resolver)
        for entry in manifest:
            if observability is not None:
                observability.record_registration_started(
                    step_name=entry.step_name,
                    service_name=entry.service_name,
                )
            result = invoker.invoke(entry, registry)
            report.add(
                name=result.service_name,
                service_type=result.service_type,
                implementation_type=result.implementation_type,
                dependencies=result.dependencies,
            )
            if entry.service_name == RuntimeServiceName.OBSERVABILITY:
                observability = registry.get(RuntimeServiceName.OBSERVABILITY)
                observability.record_boot_started()
                observability.record_manifest_loaded(entries_count=len(manifest))
                observability.record_manifest_validated()
            if observability is not None:
                observability.record_registration_completed(
                    step_name=entry.step_name,
                    service_name=result.service_name,
                    service_type=result.service_type,
                    implementation_type=result.implementation_type,
                )
        validate_runtime_boot(registry)
        if observability is not None:
            observability.record_boot_validated()
        registry.seal()
        if observability is not None:
            observability.record_registry_sealed()
        ro_registry = ReadOnlyRuntimeRegistry(registry)
        exports = build_runtime_service_exports(ro_registry)
        fingerprint = build_boot_fingerprint(report)
        return BuiltRuntime(
            registry=registry,
            report=report,
            exports=exports,
            fingerprint=fingerprint,
        )


def build_runtime() -> BuiltRuntime:
    builder = RuntimeBuilder(resolver=RuntimeDependencyResolver())
    return builder.build_runtime()


__all__ = [
    "CANON_RUNTIME_BUILDER_INTERNAL_ONLY",
    "CANON_RUNTIME_BUILDER_NO_PUBLIC_ENTRYPOINT",
    "CANON_RUNTIME_BUILDER_OWNER",
    "CANON_RUNTIME_BOOTSTRAP_RUNTIME_BUILDER_EXPLICIT_EXPORTS_ONLY",
    "BuiltRuntime",
    "RuntimeBuilder",
    "build_runtime",
]

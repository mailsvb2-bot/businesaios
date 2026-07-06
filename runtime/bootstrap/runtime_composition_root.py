"""Canonical runtime composition root for sovereign bootstrap."""

from __future__ import annotations

from dataclasses import dataclass

from runtime.bootstrap.bootstrap_contract import (
    BootstrapArtifacts,
    BootstrapAttestationPolicy,
    BootstrapEnvironment,
)
from runtime.bootstrap.bootstrap_failfast import BootstrapCompositionError
from runtime.bootstrap.startup_validator import validate_composition_artifacts

CANON_RUNTIME_BOOTSTRAP_COMPOSITION_ROOT_EXPLICIT_EXPORTS_ONLY = True

@dataclass(frozen=True)
class RuntimeCompositionResult:
    environment: BootstrapEnvironment
    artifacts: BootstrapArtifacts
def compose_runtime(
    *,
    env: BootstrapEnvironment,
    runtime_builder,
    policy: BootstrapAttestationPolicy,
) -> RuntimeCompositionResult:
    built = runtime_builder()
    required_attrs = ("registry", "report", "exports", "fingerprint")
    missing = tuple(name for name in required_attrs if not hasattr(built, name))
    if missing:
        raise BootstrapCompositionError(
            f"INCOMPLETE_RUNTIME_BUILDER_RESULT: missing={missing!r}"
        )
    validate_composition_artifacts(
        registry=built.registry,
        report=built.report,
        exports=built.exports,
        policy=policy,
    )
    artifacts = BootstrapArtifacts(
        registry=built.registry,
        report=built.report,
        exports=built.exports,
        fingerprint=built.fingerprint,
        built_runtime=built,
    )
    return RuntimeCompositionResult(environment=env, artifacts=artifacts)


__all__ = [
    "CANON_RUNTIME_BOOTSTRAP_COMPOSITION_ROOT_EXPLICIT_EXPORTS_ONLY",
    "RuntimeCompositionResult",
    "compose_runtime",
]

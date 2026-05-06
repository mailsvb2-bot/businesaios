from __future__ import annotations

from runtime.service_names import RuntimeServiceName
from dataclasses import fields, is_dataclass
from runtime.application.contracts import RuntimeServiceExports
from runtime.bootstrap.bootstrap_contract import (
    BootstrapAttestationPolicy,
    BootstrapEnvironment,
    BootstrapFailureCode,
    BootstrapMode,
)
from runtime.bootstrap.bootstrap_failfast import BootstrapAttestationError, raise_failfast
from runtime.bootstrap.entrypoint_manifest import canonical_bootstrap_surface_manifest
from runtime.lifecycle import RuntimeLifecycle
from pathlib import Path
import tempfile
def _ensure_runtime_dir(env: BootstrapEnvironment) -> None:
    runtime_dir = env.runtime_dir
    if runtime_dir.exists() and not runtime_dir.is_dir():
        raise_failfast(
            BootstrapFailureCode.RUNTIME_DIR_INVALID,
            "runtime_dir exists but is not a directory",
            path=str(runtime_dir),
        )
    try:
        runtime_dir.mkdir(parents=True, exist_ok=True)
        return
    except PermissionError:
        if env.mode is not BootstrapMode.TEST:
            raise
        fallback = Path(tempfile.gettempdir()) / "businesaios-runtime" / env.project_root.name
        fallback.mkdir(parents=True, exist_ok=True)
        object.__setattr__(env, "runtime_dir", fallback.resolve())

def validate_startup_environment(env: BootstrapEnvironment) -> None:
    if not env.project_root.exists():
        raise_failfast(
            BootstrapFailureCode.ROOT_MISSING,
            "project root does not exist",
            path=str(env.project_root),
        )
    _ensure_runtime_dir(env)
    if env.strict and env.release_attestation_required and not env.release_manifest_path.exists():
        raise_failfast(
            BootstrapFailureCode.RELEASE_MANIFEST_MISSING,
            "strict bootstrap requires release manifest",
            path=str(env.release_manifest_path),
        )
def validate_single_bootstrap_path(*, loaded_modules: set[str], env: BootstrapEnvironment) -> None:
    if env.allow_legacy_entrypoints:
        return
    manifest = canonical_bootstrap_surface_manifest()
    imported_legacy = tuple(
        sorted(name for name in loaded_modules if manifest.is_legacy_entrypoint(name))
    )
    if imported_legacy:
        raise_failfast(
            BootstrapFailureCode.LEGACY_ENTRYPOINT_DETECTED,
            "legacy bootstrap entrypoints imported during sovereign startup",
            modules=imported_legacy,
        )
def _expected_runtime_export_fields() -> tuple[str, ...]:
    if not is_dataclass(RuntimeServiceExports):
        return ("decision_execution", RuntimeServiceName.OBSERVABILITY)
    return tuple(field.name for field in fields(RuntimeServiceExports))
def validate_composition_artifacts(
    *,
    registry: object,
    report: object,
    exports: object,
    policy: BootstrapAttestationPolicy,
) -> None:
    if registry is None:
        raise_failfast(
            BootstrapFailureCode.REGISTRY_MISSING,
            "composition root returned empty registry",
        )
    if report is None:
        raise_failfast(
            BootstrapFailureCode.REPORT_MISSING,
            "composition root returned empty boot report",
        )
    if exports is None:
        raise_failfast(
            BootstrapFailureCode.EXPORTS_MISSING,
            "composition root returned empty service exports",
        )
    if policy.require_sealed_registry:
        lifecycle = getattr(registry, "lifecycle", None)
        if lifecycle is not RuntimeLifecycle.SEALED:
            raise_failfast(
                BootstrapFailureCode.REGISTRY_NOT_SEALED,
                "runtime registry must be sealed before sovereign runtime is published",
                lifecycle=repr(lifecycle),
            )
    if policy.require_runtime_exports_contract:
        expected_fields = _expected_runtime_export_fields()
        missing = tuple(name for name in expected_fields if not hasattr(exports, name))
        if missing:
            raise_failfast(
                BootstrapFailureCode.EXPORTS_INCOMPLETE,
                "runtime exports are missing required surfaces",
                missing=missing,
            )
def validate_attestation_alignment(
    *,
    policy: BootstrapAttestationPolicy,
    env: BootstrapEnvironment,
    registry_service_names: tuple[str, ...],
    report_service_names: tuple[str, ...],
    manifest_hash: str | None,
) -> None:
    if (
        policy.require_manifest_hash_in_prod
        and env.mode is BootstrapMode.PROD
        and env.release_attestation_required
        and not manifest_hash
    ):
        raise BootstrapAttestationError(BootstrapFailureCode.MANIFEST_HASH_REQUIRED.value)
    if policy.require_registry_report_alignment and registry_service_names != report_service_names:
        raise BootstrapAttestationError(
            f"{BootstrapFailureCode.REGISTRY_REPORT_MISMATCH.value}: "
            f"registry={registry_service_names!r} report={report_service_names!r}"
        )


# Thin compatibility aliases for legacy shim surfaces.
def validate_bootstrap_environment(env: BootstrapEnvironment) -> None:
    validate_startup_environment(env)


def validate_bootstrap_artifacts(
    *, registry: object, report: object, exports: object, policy: BootstrapAttestationPolicy
) -> None:
    validate_composition_artifacts(
        registry=registry,
        report=report,
        exports=exports,
        policy=policy,
    )

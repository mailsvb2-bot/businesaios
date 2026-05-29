from __future__ import annotations

import hashlib
from datetime import datetime, timezone, UTC
from pathlib import Path

from runtime.bootstrap.bootstrap_contract import (
    BOOTSTRAP_CONTRACT_VERSION,
    BootstrapArtifacts,
    BootstrapAttestation,
    BootstrapAttestationPolicy,
    BootstrapDiagnostics,
    BootstrapEnvironment,
)
from runtime.bootstrap.startup_validator import validate_attestation_alignment


def _sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
def _extract_registry_service_names(registry: object) -> tuple[str, ...]:
    snapshot = registry.snapshot()
    names = getattr(snapshot, "service_names", None)
    if isinstance(names, tuple):
        return tuple(sorted(str(name) for name in names))
    if isinstance(names, list):
        return tuple(sorted(str(name) for name in names))
    if isinstance(snapshot, dict) and "service_names" in snapshot:
        raw = snapshot["service_names"]
        return tuple(sorted(str(name) for name in raw))
    return ()
def _extract_report_service_names(report: object) -> tuple[str, ...]:
    method = getattr(report, "service_names", None)
    if callable(method):
        raw = method()
        return tuple(sorted(str(name) for name in raw))
    return ()
def _extract_registry_fingerprint(fingerprint: object) -> str | None:
    for attr in ("value", "digest", "fingerprint"):
        value = getattr(fingerprint, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None
def build_bootstrap_attestation(
    *,
    env: BootstrapEnvironment,
    artifacts: BootstrapArtifacts,
    policy: BootstrapAttestationPolicy | None = None,
) -> BootstrapAttestation:
    policy = policy or BootstrapAttestationPolicy()
    registry_service_names = _extract_registry_service_names(artifacts.registry)
    report_service_names = _extract_report_service_names(artifacts.report)
    manifest_hash = _sha256_file(env.release_manifest_path)
    registry_fingerprint = _extract_registry_fingerprint(artifacts.fingerprint)
    validate_attestation_alignment(
        policy=policy,
        env=env,
        registry_service_names=registry_service_names,
        report_service_names=report_service_names,
        manifest_hash=manifest_hash,
    )
    warnings: list[str] = []
    if not registry_service_names:
        warnings.append("empty_registry_snapshot")
    if not report_service_names:
        warnings.append("empty_boot_report")
    if env.release_attestation_required and manifest_hash is None:
        warnings.append("manifest_hash_missing")
    boot_id_material = "|".join(
        [
            BOOTSTRAP_CONTRACT_VERSION,
            env.mode.value,
            str(env.project_root),
            manifest_hash or "no-manifest",
            registry_fingerprint or "no-fingerprint",
            ",".join(registry_service_names),
            ",".join(report_service_names),
        ]
    )
    boot_id = hashlib.sha256(boot_id_material.encode("utf-8")).hexdigest()
    diagnostics = BootstrapDiagnostics(
        registry_service_names=registry_service_names,
        report_service_names=report_service_names,
        runtime_builder_module="runtime.bootstrap.runtime_builder",
        composition_root_module="runtime.bootstrap.runtime_composition_root",
        warnings=tuple(warnings),
    )
    return BootstrapAttestation(
        boot_id=boot_id,
        created_at=datetime.now(UTC),
        mode=env.mode,
        entrypoint="runtime.bootstrap.sovereign_bootstrap.bootstrap_runtime",
        process_bootstrap_module="runtime.bootstrap",
        composition_root_module="runtime.bootstrap.runtime_composition_root",
        runtime_builder_module="runtime.bootstrap.runtime_builder",
        manifest_path=str(env.release_manifest_path),
        release_manifest_sha256=manifest_hash,
        registry_fingerprint=registry_fingerprint,
        service_names=registry_service_names,
        policy=policy,
        diagnostics=diagnostics,
    )

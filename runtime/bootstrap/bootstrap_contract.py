from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping
BOOTSTRAP_CONTRACT_VERSION = "sovereign-bootstrap-v3"
class BootstrapMode(str, Enum):
    DEV = "dev"
    TEST = "test"
    PROD = "prod"
class BootstrapStatus(str, Enum):
    CREATED = "created"
    STARTING = "starting"
    READY = "ready"
    FAILED = "failed"
class BootstrapFailureCode(str, Enum):
    ROOT_MISSING = "BOOTSTRAP_ROOT_MISSING"
    RUNTIME_DIR_INVALID = "BOOTSTRAP_RUNTIME_DIR_INVALID"
    RELEASE_MANIFEST_MISSING = "RELEASE_MANIFEST_MISSING"
    LEGACY_ENTRYPOINT_DETECTED = "LEGACY_BOOTSTRAP_ENTRYPOINT_DETECTED"
    REGISTRY_MISSING = "BOOTSTRAP_REGISTRY_MISSING"
    REPORT_MISSING = "BOOTSTRAP_REPORT_MISSING"
    EXPORTS_MISSING = "BOOTSTRAP_EXPORTS_MISSING"
    REGISTRY_NOT_SEALED = "BOOTSTRAP_REGISTRY_NOT_SEALED"
    EXPORTS_INCOMPLETE = "BOOTSTRAP_EXPORTS_INCOMPLETE"
    MANIFEST_HASH_REQUIRED = "ATTESTATION_MANIFEST_HASH_REQUIRED_IN_PROD"
    REGISTRY_REPORT_MISMATCH = "ATTESTATION_REGISTRY_REPORT_MISMATCH"
    LOCK_ACQUIRE_FAILED = "BOOTSTRAP_LOCK_ACQUIRE_FAILED"
    LOCK_RELEASE_FAILED = "BOOTSTRAP_LOCK_RELEASE_FAILED"
    NOT_STARTED = "SOVEREIGN_BOOTSTRAP_NOT_STARTED"
@dataclass(frozen=True)
class BootstrapEnvironment:
    mode: BootstrapMode
    project_root: Path
    runtime_dir: Path
    release_manifest_path: Path
    strict: bool
    release_attestation_required: bool
    singleton_lock_enabled: bool
    allow_legacy_entrypoints: bool = False
    extra: Mapping[str, str] = field(default_factory=dict)
@dataclass(frozen=True)
class BootstrapAttestationPolicy:
    contract_version: str = BOOTSTRAP_CONTRACT_VERSION
    require_manifest_hash_in_prod: bool = True
    require_registry_report_alignment: bool = True
    require_sealed_registry: bool = True
    require_runtime_exports_contract: bool = True
    block_legacy_entrypoints: bool = True
@dataclass(frozen=True)
class BootstrapDiagnostics:
    registry_service_names: tuple[str, ...]
    report_service_names: tuple[str, ...]
    runtime_builder_module: str
    composition_root_module: str
    warnings: tuple[str, ...] = ()
@dataclass(frozen=True)
class BootstrapAttestation:
    boot_id: str
    created_at: datetime
    mode: BootstrapMode
    entrypoint: str
    process_bootstrap_module: str
    composition_root_module: str
    runtime_builder_module: str
    manifest_path: str
    release_manifest_sha256: str | None
    registry_fingerprint: str | None
    service_names: tuple[str, ...]
    policy: BootstrapAttestationPolicy
    diagnostics: BootstrapDiagnostics
@dataclass(frozen=True)
class BootstrapArtifacts:
    registry: Any
    report: Any
    exports: Any
    fingerprint: Any
    built_runtime: Any
@dataclass(frozen=True)
class BootstrapAuditEvent:
    timestamp: datetime
    status: BootstrapStatus
    code: str
    message: str
    details: Mapping[str, str] = field(default_factory=dict)
@dataclass(frozen=True)
class SovereignRuntime:
    status: BootstrapStatus
    environment: BootstrapEnvironment
    artifacts: BootstrapArtifacts
    attestation: BootstrapAttestation
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def services(self) -> tuple[str, ...]:
        return tuple(self.attestation.service_names or ())

    @property
    def components(self) -> tuple[str, ...]:
        names: list[str] = list(self.services)
        built_runtime = getattr(self.artifacts, 'built_runtime', None)
        runtime_components = getattr(built_runtime, 'components', None)
        if runtime_components:
            names.extend(str(item) for item in runtime_components)
        return tuple(dict.fromkeys(name for name in names if str(name).strip()))

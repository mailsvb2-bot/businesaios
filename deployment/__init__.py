from __future__ import annotations

"""Canonical deployment / release / operability surface.

This namespace is strictly operational. It must not create a second decision
center and must stay subordinate to the existing runtime, bootstrap, release,
and migration owners.
"""

from deployment.health_contract import (
    CANON_DEPLOYMENT_HEALTH_CONTRACT,
    HealthCheckResult,
    HealthCheckStatus,
    HealthExceptionPolicy,
    HealthReport,
    HealthSignal,
    ReadinessSnapshot,
)
from deployment.lexicon_contract import (
    CANON_DEPLOYMENT_LEXICON_CONTRACT,
    DEPLOYMENT_NAMESPACE_ROLES,
    NamespaceRole,
    deployment_namespace_map,
    detect_deployment_namespace,
)
from deployment.release_state_store import (
    CANON_DEPLOYMENT_RELEASE_STATE_STORE,
    DeploymentStateRecord,
    DeploymentStateStore,
)
from deployment.migration_guard import (
    CANON_DEPLOYMENT_MIGRATION_GUARD,
    MigrationAssessment,
    MigrationGuard,
    MigrationGuardError,
    MigrationGuardPolicy,
    MigrationRecord,
)
from deployment.readiness_checks import (
    CANON_DEPLOYMENT_READINESS_CHECKS,
    ReadinessCheckRegistry,
    ReadinessDependencies,
    build_default_readiness_registry,
    snapshot_runtime_readiness,
)
from deployment.release_audit import (
    CANON_DEPLOYMENT_RELEASE_AUDIT,
    ReleaseAuditFinding,
    ReleaseAuditLevel,
    ReleaseAuditReport,
    ReleaseAuditService,
)
from deployment.startup_barrier_policy import (
    CANON_DEPLOYMENT_STARTUP_BARRIER_POLICY,
    StartupBarrierPolicy,
    StartupBarrierReport,
    StartupBarrierViolation,
)
from deployment.version_manifest import (
    CANON_DEPLOYMENT_VERSION_MANIFEST,
    BuildStamp,
    VersionFileDigest,
    VersionManifest,
    VersionManifestBuilder,
)

__all__ = [
    "BuildStamp",
    "CANON_DEPLOYMENT_HEALTH_CONTRACT",
    "CANON_DEPLOYMENT_LEXICON_CONTRACT",
    "CANON_DEPLOYMENT_RELEASE_STATE_STORE",
    "CANON_DEPLOYMENT_MIGRATION_GUARD",
    "CANON_DEPLOYMENT_READINESS_CHECKS",
    "CANON_DEPLOYMENT_RELEASE_AUDIT",
    "CANON_DEPLOYMENT_STARTUP_BARRIER_POLICY",
    "CANON_DEPLOYMENT_VERSION_MANIFEST",
    "DEPLOYMENT_NAMESPACE_ROLES",
    "DeploymentStateRecord",
    "DeploymentStateStore",
    "HealthCheckResult",
    "HealthCheckStatus",
    "HealthExceptionPolicy",
    "HealthReport",
    "HealthSignal",
    "NamespaceRole",
    "MigrationAssessment",
    "MigrationGuard",
    "MigrationGuardError",
    "MigrationGuardPolicy",
    "MigrationRecord",
    "ReadinessCheckRegistry",
    "ReadinessDependencies",
    "ReadinessSnapshot",
    "ReleaseAuditFinding",
    "ReleaseAuditLevel",
    "ReleaseAuditReport",
    "ReleaseAuditService",
    "StartupBarrierPolicy",
    "StartupBarrierReport",
    "StartupBarrierViolation",
    "VersionFileDigest",
    "VersionManifest",
    "VersionManifestBuilder",
    "build_default_readiness_registry",
    "deployment_namespace_map",
    "detect_deployment_namespace",
    "snapshot_runtime_readiness",
]

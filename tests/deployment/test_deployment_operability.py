from __future__ import annotations

from deployment.migration_guard import MigrationGuard, MigrationGuardError
from deployment.readiness_checks import build_default_readiness_registry
from deployment.release_audit import ReleaseAuditService
from deployment.version_manifest import VersionManifestBuilder
from interfaces.api.health_handler import HealthHandler
from runtime.runtime_orchestrator import RuntimeOrchestrator
from shared.registry import ComponentRegistry, ServiceRegistry
from storage.migration_registry import Migration, MigrationRegistry


class _Executor:
    dialect = "sqlite"

    def __init__(self) -> None:
        self.version = 0

    def execute(self, sql: str, params=None):
        return None

    def fetchone(self, sql: str, params=None):
        return None if self.version == 0 else (self.version,)

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


class _AppService:
    def startup_audit_events(self):
        return ("boot:ok",)


def _runtime() -> RuntimeOrchestrator:
    services = ServiceRegistry()
    services.register("event_bus", object())
    services.register("metrics", object())
    services.register("tracer", object())
    components = ComponentRegistry()
    components.register("decision_audit_log", object())
    components.register("action_audit_log", object())
    orchestrator = RuntimeOrchestrator(services=services, components=components)
    orchestrator.boot()
    return orchestrator


def test_readiness_registry_passes_for_booted_runtime() -> None:
    report = build_default_readiness_registry(_runtime()).run_all(service="businesaios")
    assert report.ok is True
    assert report.counts()["fail"] == 0


def test_health_handler_includes_runtime_details() -> None:
    payload = HealthHandler(application_service=_AppService(), runtime_orchestrator=_runtime()).readiness()
    assert payload.status == "ready"
    assert payload.details["runtime_readiness"]["ready"] is True
    assert payload.details["version"]


def test_migration_guard_blocks_large_jump() -> None:
    registry = MigrationRegistry(
        [
            Migration(version=1, name="v1", statements=("SELECT 1",)),
            Migration(version=2, name="v2", statements=("SELECT 1",)),
            Migration(version=3, name="v3", statements=("SELECT 1",)),
        ]
    )
    guard = MigrationGuard()
    try:
        guard.assert_safe_to_deploy(registry=registry, executor=_Executor())
    except MigrationGuardError as exc:
        assert "migration jump too large" in str(exc)
    else:
        raise AssertionError("expected migration guard to block large jump")


def test_release_audit_reports_parseable_release_manifest() -> None:
    runtime = _runtime()
    health = build_default_readiness_registry(runtime).run_all(service="businesaios")
    manifest = VersionManifestBuilder(service="businesaios").build(tracked_files=("VERSION", "RELEASE_TAG"))
    report = ReleaseAuditService().audit(manifest=manifest, health=health)
    assert report.ok is True
    assert any(item.code == "release_manifest_present" for item in report.findings)



def test_version_manifest_rejects_repo_escape_in_tracked_files() -> None:
    builder = VersionManifestBuilder(service="businesaios")
    try:
        builder.build(tracked_files=("../outside.txt",))
    except ValueError as exc:
        assert "escapes repo_root" in str(exc)
    else:
        raise AssertionError("expected repo escape guard to reject tracked file")


def test_startup_barrier_policy_rejects_repo_escape() -> None:
    from deployment.startup_barrier_policy import StartupBarrierPolicy

    policy = StartupBarrierPolicy(required_paths=("../outside.txt",))
    try:
        policy.validate_environment()
    except ValueError as exc:
        assert "escapes repo_root" in str(exc)
    else:
        raise AssertionError("expected startup barrier path guard to reject repo escape")


def test_migration_guard_accepts_dict_like_pending_records() -> None:
    class _DictRegistry:
        def current_version(self, executor, *, scope="storage", component="storage_migrations"):
            return 1

        def latest_version(self) -> int:
            return 2

        def pending(self, current_version: int):
            return ({"version": 2, "name": "v2"},)

    guard = MigrationGuard(policy=__import__("deployment.migration_guard", fromlist=["MigrationGuardPolicy"]).MigrationGuardPolicy(max_linear_jump=2))
    assessment = guard.assess(registry=_DictRegistry(), executor=object())
    assert assessment.pending_versions == (2,)
    assert assessment.blocked is False

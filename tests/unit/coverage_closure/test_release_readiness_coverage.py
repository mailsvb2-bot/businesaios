from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from deployment.health_contract import (
    HealthCheckResult,
    HealthCheckStatus,
    HealthExceptionPolicy,
    HealthReport,
    HealthSignal,
)
from deployment.migration_guard import MigrationAssessment
from deployment.readiness_checks import (
    ReadinessCheckRegistry,
    ReadinessDependencies,
    build_default_readiness_registry,
    snapshot_runtime_readiness,
)
from deployment.release_audit import ReleaseAuditLevel, ReleaseAuditService
from deployment.version_manifest import (
    BuildStamp,
    VersionFileDigest,
    VersionManifest,
    VersionManifestBuilder,
)


def _health(status: HealthCheckStatus) -> HealthReport:
    return HealthReport.aggregate(
        service="svc",
        checks=(
            HealthCheckResult(
                name="one",
                status=status,
                signal=HealthSignal.RELEASE,
                summary="checked",
            ),
        ),
    )


def test_version_manifest_builder_and_release_audit_branches(tmp_path: Path) -> None:
    (tmp_path / "release").mkdir()
    (tmp_path / "VERSION").write_text("2.3.4\n", encoding="utf-8")
    (tmp_path / "RELEASE_TAG").write_text("v2.3.4\n", encoding="utf-8")
    (tmp_path / "tracked.txt").write_text("payload", encoding="utf-8")
    release_path = tmp_path / "release/manifest.json"
    release_path.write_text(
        json.dumps({"version": "2.3.4", "release_tag": "v2.3.4", "files": {"a": "x"}}),
        encoding="utf-8",
    )
    builder = VersionManifestBuilder(service="svc", repo_root=tmp_path)
    manifest = builder.build(
        tracked_files=("tracked.txt", "tracked.txt", "missing.txt"),
        strict_missing_files=False,
        environ={"GIT_COMMIT": "abcdef1"},
        metadata={"owner": "test"},
    )
    assert manifest.build.version == "2.3.4"
    assert manifest.build.release_tag == "v2.3.4"
    assert manifest.files[0].path == "tracked.txt"
    assert manifest.metadata["missing_tracked_files"] == ("missing.txt",)
    assert json.loads(manifest.to_json())["service"] == "svc"
    with pytest.raises(FileNotFoundError):
        builder.build(tracked_files=("missing.txt",))
    with pytest.raises(ValueError, match="escapes"):
        builder.build(tracked_files=("../outside",), strict_missing_files=False)

    fallback_root = tmp_path / "fallback"
    fallback_root.mkdir()
    fallback = VersionManifestBuilder(service="fallback", repo_root=fallback_root).build(
        environ={"APP_VERSION": "9", "RELEASE_TAG": "dev", "GIT_COMMIT": "1234567"}
    )
    assert fallback.build.version == "9"

    with pytest.raises(ValueError):
        VersionFileDigest("", "0" * 64)
    with pytest.raises(ValueError):
        VersionFileDigest("a", "xyz")
    with pytest.raises(ValueError):
        BuildStamp("", "v")
    with pytest.raises(ValueError):
        BuildStamp("1", "")
    with pytest.raises(ValueError):
        BuildStamp("1", "v", "UPPER")
    with pytest.raises(ValueError):
        VersionManifest("", BuildStamp("1", "v"))
    with pytest.raises(ValueError, match="unique"):
        VersionManifest(
            "svc",
            BuildStamp("1", "v"),
            files=(VersionFileDigest("a", "0" * 64), VersionFileDigest("a", "1" * 64)),
        )
    with pytest.raises(ValueError):
        VersionManifestBuilder(service="", repo_root=tmp_path)

    service = ReleaseAuditService()
    good = service.audit(
        manifest=manifest,
        health=_health(HealthCheckStatus.PASS),
        migration=MigrationAssessment(1, 1),
        release_manifest_path=release_path,
    )
    assert good.ok and {"health_ok", "release_manifest_present", "migration_ok"} <= {f.code for f in good.findings}
    assert good.counts()[ReleaseAuditLevel.INFO.value] >= 1

    warn_manifest = VersionManifest("svc", BuildStamp("2.3.4", "v2.3.4"), constitution_version=None)
    warn = service.audit(
        manifest=warn_manifest,
        health=_health(HealthCheckStatus.WARN),
        migration=MigrationAssessment(1, 2, (2,)),
        release_manifest_path=release_path,
    )
    assert {"health_warn", "constitution_version_missing", "migration_pending"} <= {f.code for f in warn.findings}

    mismatch = VersionManifest(
        "svc",
        BuildStamp("wrong", "wrong"),
        constitution_version=1,
        release_manifest_file_count=2,
    )
    failed = service.audit(
        manifest=mismatch,
        health=_health(HealthCheckStatus.FAIL),
        migration=MigrationAssessment(1, 3, (2, 3), ("blocked",)),
        release_manifest_path=release_path,
    )
    assert not failed.ok
    assert {"health_failed", "version_mismatch", "release_tag_mismatch", "release_manifest_file_count_mismatch", "migration_blocked"} <= {f.code for f in failed.findings}

    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text("[]", encoding="utf-8")
    invalid = service.audit(manifest=manifest, health=_health(HealthCheckStatus.PASS), release_manifest_path=invalid_path)
    assert "release_manifest_invalid" in {f.code for f in invalid.findings}
    missing = service.audit(manifest=manifest, health=_health(HealthCheckStatus.PASS), release_manifest_path=tmp_path / "none")
    assert "release_manifest_missing" in {f.code for f in missing.findings}


def _orchestrator(*, services: object, components: object, booted: bool, ready: bool, gate: bool, shutting_down: bool = False):
    return SimpleNamespace(
        services=services,
        components=components,
        state=SimpleNamespace(booted=booted, ready=ready, shutting_down=shutting_down),
        readiness=SimpleNamespace(is_ready=lambda _state: gate),
    )


def test_readiness_registry_and_default_checks_cover_failure_modes() -> None:
    deps = ReadinessDependencies(required_services=("event_bus",), required_components=("audit",))
    ready = _orchestrator(services={"event_bus": 1}, components={"audit": 1}, booted=True, ready=True, gate=True)
    snap = snapshot_runtime_readiness(ready, dependencies=deps)
    assert snap.ready and snap.service_count == 1 and snap.component_count == 1
    report = build_default_readiness_registry(ready, dependencies=deps).run_all(service="svc", version="1", release_id="r")
    assert report.overall_status is HealthCheckStatus.PASS

    broken = _orchestrator(services=[], components=SimpleNamespace(names=lambda: ()), booted=False, ready=True, gate=False, shutting_down=True)
    broken_report = build_default_readiness_registry(broken, dependencies=deps).run_all(service="svc")
    assert broken_report.overall_status is HealthCheckStatus.FAIL
    summaries = " ".join(item.summary for item in broken_report.checks)
    assert "runtime not booted" in summaries and "registries are empty" in summaries

    registry = ReadinessCheckRegistry(exception_policy=HealthExceptionPolicy.WARN_OPEN)
    with pytest.raises(ValueError):
        registry.register("", lambda: None)
    registry.register("boom", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    with pytest.raises(ValueError, match="duplicate"):
        registry.register("boom", lambda: None)
    registry.register(
        "mismatch",
        lambda: HealthCheckResult("wrong", HealthCheckStatus.PASS, HealthSignal.READINESS, "ok"),
    )
    custom = registry.run_all(service="svc")
    assert custom.checks[0].status is HealthCheckStatus.WARN
    assert custom.checks[1].status is HealthCheckStatus.FAIL
    assert registry.names() == ("boom", "mismatch")
    with pytest.raises(ValueError, match="at least one"):
        ReadinessCheckRegistry().run_all(service="svc")
    with pytest.raises(ValueError, match="unique"):
        ReadinessDependencies(required_services=("x", "x"))

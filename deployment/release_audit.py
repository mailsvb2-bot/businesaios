from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
import json

from deployment.health_contract import HealthCheckStatus, HealthReport
from deployment.migration_guard import MigrationAssessment
from deployment.version_manifest import VersionManifest


CANON_DEPLOYMENT_RELEASE_AUDIT = True


class ReleaseAuditLevel(StrEnum):
    INFO = "info"
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True)
class ReleaseAuditFinding:
    code: str
    level: ReleaseAuditLevel
    summary: str
    details: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.code or "").strip():
            raise ValueError("release audit finding code is required")
        if not str(self.summary or "").strip():
            raise ValueError("release audit finding summary is required")


@dataclass(frozen=True)
class ReleaseAuditReport:
    service: str
    findings: tuple[ReleaseAuditFinding, ...]
    generated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @property
    def ok(self) -> bool:
        return not any(item.level is ReleaseAuditLevel.FAIL for item in self.findings)

    def counts(self) -> dict[str, int]:
        return {
            level.value: sum(1 for item in self.findings if item.level is level)
            for level in ReleaseAuditLevel
        }


class ReleaseAuditService:
    def audit(
        self,
        *,
        manifest: VersionManifest,
        health: HealthReport,
        migration: MigrationAssessment | None = None,
        release_manifest_path: str | Path = "release/manifest.json",
    ) -> ReleaseAuditReport:
        findings: list[ReleaseAuditFinding] = []
        if health.overall_status is HealthCheckStatus.FAIL:
            findings.append(
                ReleaseAuditFinding(
                    code="health_failed",
                    level=ReleaseAuditLevel.FAIL,
                    summary="health report contains failing checks",
                    details={"counts": health.counts()},
                )
            )
        elif health.overall_status is HealthCheckStatus.WARN:
            findings.append(
                ReleaseAuditFinding(
                    code="health_warn",
                    level=ReleaseAuditLevel.WARN,
                    summary="health report contains warnings",
                    details={"counts": health.counts()},
                )
            )
        else:
            findings.append(
                ReleaseAuditFinding(
                    code="health_ok",
                    level=ReleaseAuditLevel.INFO,
                    summary="health report passed",
                    details={"counts": health.counts()},
                )
            )

        if manifest.constitution_version is None:
            findings.append(
                ReleaseAuditFinding(
                    code="constitution_version_missing",
                    level=ReleaseAuditLevel.WARN,
                    summary="constitution version was not resolved into manifest",
                )
            )
        else:
            findings.append(
                ReleaseAuditFinding(
                    code="constitution_version_present",
                    level=ReleaseAuditLevel.INFO,
                    summary="constitution version resolved into manifest",
                    details={"constitution_version": manifest.constitution_version},
                )
            )

        release_manifest = Path(release_manifest_path)
        if not release_manifest.exists():
            findings.append(
                ReleaseAuditFinding(
                    code="release_manifest_missing",
                    level=ReleaseAuditLevel.FAIL,
                    summary="release/manifest.json is missing",
                    details={"path": str(release_manifest)},
                )
            )
        else:
            try:
                payload = json.loads(release_manifest.read_text(encoding="utf-8"))
                files = payload.get("files") or {}
                if not isinstance(files, dict):
                    raise TypeError("manifest.files must be a dict")
                release_tag = None if payload.get("release_tag") is None else str(payload.get("release_tag"))
                version = None if payload.get("version") is None else str(payload.get("version"))
                findings.append(
                    ReleaseAuditFinding(
                        code="release_manifest_present",
                        level=ReleaseAuditLevel.INFO,
                        summary="release manifest is present and parseable",
                        details={
                            "files_count": len(files),
                            "path": str(release_manifest),
                            "release_tag": release_tag,
                            "version": version,
                        },
                    )
                )
                if version is not None and version != manifest.build.version:
                    findings.append(
                        ReleaseAuditFinding(
                            code="version_mismatch",
                            level=ReleaseAuditLevel.FAIL,
                            summary="VERSION does not match release manifest version",
                            details={"manifest_version": manifest.build.version, "release_manifest_version": version},
                        )
                    )
                if release_tag is not None and release_tag != manifest.build.release_tag:
                    findings.append(
                        ReleaseAuditFinding(
                            code="release_tag_mismatch",
                            level=ReleaseAuditLevel.FAIL,
                            summary="RELEASE_TAG does not match release manifest release_tag",
                            details={"manifest_release_tag": manifest.build.release_tag, "release_manifest_release_tag": release_tag},
                        )
                    )
                if manifest.release_manifest_file_count is not None and manifest.release_manifest_file_count != len(files):
                    findings.append(
                        ReleaseAuditFinding(
                            code="release_manifest_file_count_mismatch",
                            level=ReleaseAuditLevel.FAIL,
                            summary="embedded release manifest metadata does not match parsed manifest",
                            details={
                                "embedded_count": manifest.release_manifest_file_count,
                                "parsed_count": len(files),
                            },
                        )
                    )
            except Exception as exc:
                findings.append(
                    ReleaseAuditFinding(
                        code="release_manifest_invalid",
                        level=ReleaseAuditLevel.FAIL,
                        summary="release manifest is invalid",
                        details={"path": str(release_manifest), "error_type": type(exc).__name__, "error": str(exc)},
                    )
                )

        if migration is not None:
            if migration.blocked:
                findings.append(
                    ReleaseAuditFinding(
                        code="migration_blocked",
                        level=ReleaseAuditLevel.FAIL,
                        summary="release is blocked by migration guard",
                        details={
                            "current_version": migration.current_version,
                            "target_version": migration.target_version,
                            "pending_versions": migration.pending_versions,
                            "reasons": migration.reasons,
                        },
                    )
                )
            elif migration.pending_versions:
                findings.append(
                    ReleaseAuditFinding(
                        code="migration_pending",
                        level=ReleaseAuditLevel.WARN,
                        summary="release has unapplied migrations",
                        details={"pending_versions": migration.pending_versions},
                    )
                )
            else:
                findings.append(
                    ReleaseAuditFinding(
                        code="migration_ok",
                        level=ReleaseAuditLevel.INFO,
                        summary="migration guard passed",
                        details={"target_version": migration.target_version},
                    )
                )

        return ReleaseAuditReport(service=manifest.service, findings=tuple(findings))


__all__ = [
    "CANON_DEPLOYMENT_RELEASE_AUDIT",
    "ReleaseAuditFinding",
    "ReleaseAuditLevel",
    "ReleaseAuditReport",
    "ReleaseAuditService",
]

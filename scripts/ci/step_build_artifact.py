from __future__ import annotations

import json
import zipfile
from pathlib import Path

from core.security.release_runtime_surface import runtime_release_member_violations
from scripts.ci.artifact_manifest import iter_project_files, sha256_file
from scripts.ci.paths import dist_dir, repo_root

_FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def _version() -> str:
    version_file = repo_root() / "VERSION"
    if version_file.exists():
        value = version_file.read_text(encoding="utf-8").strip()
        if value:
            return value
    return "0.0.0"


def _artifact_report_path() -> Path:
    return repo_root() / "artifacts" / "ci" / "release_artifact.json"


def _write_artifact_report(payload: dict[str, object]) -> None:
    path = _artifact_report_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _zip_info(path: Path, rel: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(rel, date_time=_FIXED_ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (path.stat().st_mode & 0xFFFF) << 16
    return info


def _remove_previous_artifacts(artifact: Path, checksum: Path) -> None:
    artifact.unlink(missing_ok=True)
    checksum.unlink(missing_ok=True)


def run() -> tuple[bool, str]:
    root = repo_root()
    dist = dist_dir()
    version = _version()
    artifact = dist / f"BUSINESAIOS_{version}_release.zip"
    checksum = dist / f"{artifact.name}.sha256"
    _remove_previous_artifacts(artifact, checksum)

    files = [
        path
        for path in iter_project_files(root)
        if dist not in path.parents
    ]
    members = [path.relative_to(root).as_posix() for path in files]
    violations = runtime_release_member_violations(members)
    if violations:
        _write_artifact_report(
            {
                "artifact": "release_artifact",
                "status": "blocked",
                "violations": list(violations),
                "claims_production_ready": False,
            }
        )
        return False, "release artifact blocked: " + ",".join(violations[:10])

    uncompressed_bytes = 0
    with zipfile.ZipFile(
        artifact,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path, rel in zip(files, members, strict=True):
            payload = path.read_bytes()
            uncompressed_bytes += len(payload)
            archive.writestr(_zip_info(path, rel), payload)

    with zipfile.ZipFile(artifact) as archive:
        archived_members = archive.namelist()
    archive_violations = runtime_release_member_violations(archived_members)
    if archive_violations or archived_members != members:
        artifact.unlink(missing_ok=True)
        violations = list(archive_violations)
        if archived_members != members:
            violations.append("archive_member_order_or_content_mismatch")
        _write_artifact_report(
            {
                "artifact": "release_artifact",
                "status": "blocked",
                "violations": sorted(set(violations)),
                "claims_production_ready": False,
            }
        )
        return False, "release artifact verification failed: " + ",".join(
            sorted(set(violations))[:10]
        )

    digest = sha256_file(artifact)
    checksum.write_text(
        f"{digest}  {artifact.name}\n",
        encoding="utf-8",
    )
    report = {
        "artifact": "release_artifact",
        "status": "ready",
        "filename": artifact.name,
        "sha256": digest,
        "file_count": len(members),
        "archive_bytes": artifact.stat().st_size,
        "uncompressed_bytes": uncompressed_bytes,
        "deterministic_zip_timestamp": list(_FIXED_ZIP_TIMESTAMP),
        "violations": [],
        "claims_production_ready": False,
    }
    _write_artifact_report(report)
    return True, (
        f"artifact built: {artifact.name}; files={len(members)}; "
        f"bytes={artifact.stat().st_size}; sha256={digest}"
    )


__all__ = ["run"]

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Mapping, Sequence
import json
import os
import re


CANON_DEPLOYMENT_VERSION_MANIFEST = True

_GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{7,64}$")


@dataclass(frozen=True)
class VersionFileDigest:
    path: str
    sha256: str

    def __post_init__(self) -> None:
        normalized_path = str(self.path or "").strip()
        digest = str(self.sha256 or "").strip().lower()
        if not normalized_path:
            raise ValueError("digest path is required")
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError("digest sha256 must be a 64-character lowercase hex string")


@dataclass(frozen=True)
class BuildStamp:
    version: str
    release_tag: str
    git_commit: str | None = None
    built_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def __post_init__(self) -> None:
        if not str(self.version or "").strip():
            raise ValueError("build version is required")
        if not str(self.release_tag or "").strip():
            raise ValueError("release_tag is required")
        if self.git_commit is not None and not _GIT_COMMIT_RE.match(str(self.git_commit)):
            raise ValueError("git_commit must be 7..64 lowercase hex characters")


@dataclass(frozen=True)
class VersionManifest:
    service: str
    build: BuildStamp
    constitution_version: int | None = None
    files: tuple[VersionFileDigest, ...] = field(default_factory=tuple)
    release_manifest_file_count: int | None = None
    release_manifest_sha256: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.service or "").strip():
            raise ValueError("service is required")
        file_paths = tuple(item.path for item in self.files)
        if len(set(file_paths)) != len(file_paths):
            raise ValueError("manifest files must be unique by path")

    def to_dict(self) -> dict[str, object]:
        return {
            "service": self.service,
            "build": {
                "version": self.build.version,
                "release_tag": self.build.release_tag,
                "git_commit": self.build.git_commit,
                "built_at": self.build.built_at,
            },
            "constitution_version": self.constitution_version,
            "release_manifest_file_count": self.release_manifest_file_count,
            "release_manifest_sha256": self.release_manifest_sha256,
            "files": [
                {"path": item.path, "sha256": item.sha256}
                for item in self.files
            ],
            "metadata": dict(self.metadata),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"


class VersionManifestBuilder:
    def __init__(self, *, service: str, repo_root: str | Path = ".") -> None:
        normalized = str(service or "").strip()
        if not normalized:
            raise ValueError("service is required")
        self._service = normalized
        self._repo_root = Path(repo_root).resolve()

    def _resolve_relative_file(self, relative_path: str) -> tuple[Path, str]:
        normalized = str(relative_path or "").strip().replace("\\", "/")
        if not normalized:
            raise ValueError("tracked file path is required")
        candidate = (self._repo_root / normalized).resolve()
        try:
            candidate.relative_to(self._repo_root)
        except ValueError as exc:
            raise ValueError(f"tracked file escapes repo_root: {normalized}") from exc
        return candidate, candidate.relative_to(self._repo_root).as_posix()

    def _read_text(self, relative_path: str) -> str:
        path, _ = self._resolve_relative_file(relative_path)
        return path.read_text(encoding="utf-8").strip()

    def _file_digest(self, relative_path: str) -> VersionFileDigest:
        path, normalized = self._resolve_relative_file(relative_path)
        payload = path.read_bytes()
        return VersionFileDigest(path=normalized, sha256=sha256(payload).hexdigest())

    def _load_constitution_version(self) -> int | None:
        try:
            from governance.version import CONSTITUTION_VERSION
            return int(CONSTITUTION_VERSION)
        except Exception:
            return None

    def _load_release_manifest_metadata(self) -> tuple[int | None, str | None, str | None, str | None]:
        manifest_path, _ = self._resolve_relative_file("release/manifest.json")
        if not manifest_path.exists():
            return None, None, None, None
        payload = manifest_path.read_bytes()
        manifest_sha = sha256(payload).hexdigest()
        try:
            data = json.loads(payload.decode("utf-8"))
        except Exception:
            return None, manifest_sha, None, None
        files = data.get("files") or {}
        file_count = len(files) if isinstance(files, dict) else None
        release_tag = data.get("release_tag")
        version = data.get("version")
        return file_count, manifest_sha, None if release_tag is None else str(release_tag), None if version is None else str(version)

    def build(
        self,
        *,
        tracked_files: Sequence[str] = (),
        metadata: Mapping[str, object] | None = None,
        environ: Mapping[str, str] | None = None,
        strict_missing_files: bool = True,
    ) -> VersionManifest:
        env = dict(os.environ if environ is None else environ)
        version_path, _ = self._resolve_relative_file("VERSION")
        release_tag_path, _ = self._resolve_relative_file("RELEASE_TAG")
        version = self._read_text("VERSION") if version_path.exists() else str(env.get("APP_VERSION", "0.0.0")).strip()
        release_tag = self._read_text("RELEASE_TAG") if release_tag_path.exists() else str(env.get("RELEASE_TAG", "dev")).strip()
        git_commit = str(env.get("GIT_COMMIT", "")).strip().lower() or None
        constitution_version = self._load_constitution_version()
        release_manifest_file_count, release_manifest_sha256, release_manifest_tag, release_manifest_version = self._load_release_manifest_metadata()
        normalized_tracked = tuple(sorted({self._resolve_relative_file(str(item).strip())[1] for item in tracked_files if str(item).strip()}))
        missing_files = tuple(path for path in normalized_tracked if not self._resolve_relative_file(path)[0].exists())
        if strict_missing_files and missing_files:
            raise FileNotFoundError(f"tracked files missing: {missing_files}")
        files = tuple(
            self._file_digest(item)
            for item in normalized_tracked
            if self._resolve_relative_file(item)[0].exists()
        )
        merged_metadata = dict(metadata or {})
        if missing_files:
            merged_metadata.setdefault("missing_tracked_files", missing_files)
        if release_manifest_tag is not None:
            merged_metadata.setdefault("release_manifest_tag", release_manifest_tag)
        if release_manifest_version is not None:
            merged_metadata.setdefault("release_manifest_version", release_manifest_version)
        return VersionManifest(
            service=self._service,
            build=BuildStamp(version=version, release_tag=release_tag, git_commit=git_commit),
            constitution_version=constitution_version,
            files=files,
            release_manifest_file_count=release_manifest_file_count,
            release_manifest_sha256=release_manifest_sha256,
            metadata=merged_metadata,
        )


__all__ = [
    "BuildStamp",
    "CANON_DEPLOYMENT_VERSION_MANIFEST",
    "VersionFileDigest",
    "VersionManifest",
    "VersionManifestBuilder",
]

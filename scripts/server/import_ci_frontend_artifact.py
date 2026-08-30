from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from runtime._internal.http_transport import sync_get

REPOSITORY = "mailsvb2-bot/businesaios"
REPOSITORY_ID = 1231282346
PRODUCTION_ROOT = Path("/opt/businesaios")
REQUEST_DIR = Path("/var/lib/businesaios/rdc-deploy-request")
ARTIFACT_ZIP = REQUEST_DIR / "frontend-dist.zip"
ARTIFACT_ID = REQUEST_DIR / "frontend-dist.artifact-id"
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def _fail(message: str) -> RuntimeError:
    return RuntimeError(f"CI frontend artifact import refused: {message}")


def _json_get(url: str) -> dict[str, object]:
    response = sync_get(
        url=url,
        headers={"Accept": "application/vnd.github+json"},
        timeout_s=15,
    )
    if response.status != 200 or not isinstance(response.json, dict):
        raise _fail(f"GitHub metadata request failed with status {response.status}")
    return response.json


def _expected_sha() -> str:
    sha = os.environ.get("EXPECTED_SHA", "").strip().lower()
    if len(sha) != 40 or any(ch not in "0123456789abcdef" for ch in sha):
        raise _fail("EXPECTED_SHA must expose the full lowercase deployed SHA")
    return sha


def _validate_metadata(artifact_id: int, expected_sha: str, zip_bytes: bytes) -> None:
    artifact = _json_get(f"https://api.github.com/repos/{REPOSITORY}/actions/artifacts/{artifact_id}")
    if artifact.get("name") != "frontend-dist" or artifact.get("expired") is not False:
        raise _fail("artifact metadata is not an active frontend-dist artifact")
    workflow = artifact.get("workflow_run")
    if not isinstance(workflow, dict):
        raise _fail("artifact metadata is missing workflow_run")
    if workflow.get("repository_id") != REPOSITORY_ID or workflow.get("head_repository_id") != REPOSITORY_ID:
        raise _fail("artifact repository identity mismatch")
    if workflow.get("head_branch") != "main" or workflow.get("head_sha") != expected_sha:
        raise _fail("artifact is not bound to the exact deployed main SHA")
    digest = str(artifact.get("digest") or "")
    actual_digest = f"sha256:{hashlib.sha256(zip_bytes).hexdigest()}"
    if digest != actual_digest:
        raise _fail("artifact archive digest does not match GitHub metadata")

    run_id = workflow.get("id")
    if not isinstance(run_id, int):
        raise _fail("artifact workflow run id is missing")
    run = _json_get(f"https://api.github.com/repos/{REPOSITORY}/actions/runs/{run_id}")
    required = {
        "event": "push",
        "status": "completed",
        "conclusion": "success",
        "head_branch": "main",
        "head_sha": expected_sha,
        "path": ".github/workflows/ci.yml",
    }
    for key, expected in required.items():
        if run.get(key) != expected:
            raise _fail(f"workflow run {key} is not {expected!r}")


def _validate_and_extract(zip_bytes: bytes, expected_sha: str, destination: Path) -> None:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        names: set[str] = set()
        for info in archive.infolist():
            relative = PurePosixPath(info.filename)
            if relative.is_absolute() or ".." in relative.parts or not relative.parts:
                raise _fail(f"unsafe artifact path: {info.filename!r}")
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise _fail(f"artifact symlink is not allowed: {info.filename!r}")
            if not info.is_dir():
                names.add(relative.as_posix())
        if "release-manifest.json" not in names:
            raise _fail("artifact does not contain release-manifest.json")
        archive.extractall(destination)

    manifest_path = destination / "release-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or manifest.get("commit_sha") != expected_sha:
        raise _fail("release manifest is not bound to the exact deployed SHA")
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise _fail("release manifest files map is invalid")
    actual_files = {
        path.relative_to(destination).as_posix()
        for path in destination.rglob("*")
        if path.is_file() and path != manifest_path
    }
    if set(files) != actual_files:
        raise _fail("artifact files do not exactly match release manifest")
    for relative, expected_digest in files.items():
        path = destination.joinpath(*PurePosixPath(str(relative)).parts)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != str(expected_digest).lower():
            raise _fail(f"release manifest hash mismatch: {relative}")


def main() -> int:
    zip_exists = ARTIFACT_ZIP.exists()
    id_exists = ARTIFACT_ID.exists()
    production_checkout = DIST.parents[1] == PRODUCTION_ROOT
    if not zip_exists and not id_exists:
        if production_checkout:
            raise _fail("canonical production build requires a staged frontend-dist artifact and artifact id")
        return 0
    if zip_exists != id_exists:
        raise _fail("staged artifact zip/id pair is incomplete")
    if ARTIFACT_ZIP.is_symlink() or ARTIFACT_ID.is_symlink():
        raise _fail("staged artifact inputs must not be symlinks")

    expected_sha = _expected_sha()
    artifact_id_text = ARTIFACT_ID.read_text(encoding="ascii").strip()
    if not artifact_id_text.isdecimal():
        raise _fail("artifact id must be decimal")
    artifact_id = int(artifact_id_text)
    zip_bytes = ARTIFACT_ZIP.read_bytes()
    _validate_metadata(artifact_id, expected_sha, zip_bytes)

    parent = DIST.parent
    temp = Path(tempfile.mkdtemp(prefix=".dist-ci-import-", dir=parent))
    backup = parent / f".dist-pre-ci-{os.getpid()}"
    try:
        _validate_and_extract(zip_bytes, expected_sha, temp)
        if DIST.exists():
            DIST.rename(backup)
        temp.rename(DIST)
        shutil.rmtree(backup, ignore_errors=True)
    except Exception:
        if not DIST.exists() and backup.exists():
            backup.rename(DIST)
        shutil.rmtree(temp, ignore_errors=True)
        raise

    ARTIFACT_ZIP.unlink()
    ARTIFACT_ID.unlink()
    print(f"CI_FRONTEND_ARTIFACT_IMPORTED sha={expected_sha} artifact_id={artifact_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

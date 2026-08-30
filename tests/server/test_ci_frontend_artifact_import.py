from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

from scripts.server import import_ci_frontend_artifact as importer

SHA = "a" * 40


def _bundle(*, sha: str = SHA, index: bytes = b"<html></html>") -> bytes:
    files = {
        "index.html": index,
        "assets/app.js": b"console.log('ok')\n",
    }
    manifest = {
        "schema_version": 1,
        "commit_sha": sha,
        "files": {name: hashlib.sha256(content).hexdigest() for name, content in files.items()},
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
        archive.writestr("release-manifest.json", json.dumps(manifest))
    return buffer.getvalue()


def test_validate_and_extract_accepts_exact_manifest(tmp_path: Path) -> None:
    importer._validate_and_extract(_bundle(), SHA, tmp_path)
    assert (tmp_path / "index.html").is_file()
    assert (tmp_path / "assets/app.js").is_file()


def test_validate_and_extract_rejects_tampered_file(tmp_path: Path) -> None:
    raw = _bundle()
    source = zipfile.ZipFile(io.BytesIO(raw))
    buffer = io.BytesIO()
    with source, zipfile.ZipFile(buffer, "w") as target:
        for info in source.infolist():
            content = source.read(info.filename)
            if info.filename == "index.html":
                content = b"tampered"
            target.writestr(info, content)
    with pytest.raises(RuntimeError, match="release manifest hash mismatch"):
        importer._validate_and_extract(buffer.getvalue(), SHA, tmp_path)


def test_validate_and_extract_rejects_path_traversal(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../escape.txt", b"bad")
        archive.writestr("release-manifest.json", b"{}")
    with pytest.raises(RuntimeError, match="unsafe artifact path"):
        importer._validate_and_extract(buffer.getvalue(), SHA, tmp_path)


def test_validate_metadata_requires_successful_exact_main_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = _bundle()
    artifact_id = 123
    artifact = {
        "name": "frontend-dist",
        "expired": False,
        "digest": f"sha256:{hashlib.sha256(bundle).hexdigest()}",
        "workflow_run": {
            "id": 456,
            "repository_id": importer.REPOSITORY_ID,
            "head_repository_id": importer.REPOSITORY_ID,
            "head_branch": "main",
            "head_sha": SHA,
        },
    }
    run = {
        "event": "push",
        "status": "completed",
        "conclusion": "success",
        "head_branch": "main",
        "head_sha": SHA,
        "path": ".github/workflows/ci.yml",
    }

    monkeypatch.setattr(importer, "_json_get", lambda url: run if url.endswith("/456") else artifact)
    importer._validate_metadata(artifact_id, SHA, bundle)

    artifact["workflow_run"]["head_sha"] = "b" * 40
    with pytest.raises(RuntimeError, match="exact deployed main SHA"):
        importer._validate_metadata(artifact_id, SHA, bundle)

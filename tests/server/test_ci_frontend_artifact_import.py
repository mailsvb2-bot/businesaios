from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

from runtime import effects as runtime_effects
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


def test_expected_sha_requires_explicit_deploy_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXPECTED_SHA", raising=False)
    with pytest.raises(RuntimeError, match="EXPECTED_SHA must expose"):
        importer._expected_sha()
    monkeypatch.setenv("EXPECTED_SHA", SHA)
    assert importer._expected_sha() == SHA


def test_main_requires_staged_pair_in_canonical_production(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(importer, "DIST", importer.PRODUCTION_ROOT / "frontend" / "dist")
    monkeypatch.setattr(importer, "ARTIFACT_ZIP", tmp_path / "missing.zip")
    monkeypatch.setattr(importer, "ARTIFACT_ID", tmp_path / "missing.id")
    with pytest.raises(RuntimeError, match="canonical production build requires"):
        importer.main()


def test_main_allows_noop_outside_canonical_production(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(importer, "DIST", tmp_path / "checkout" / "frontend" / "dist")
    monkeypatch.setattr(importer, "ARTIFACT_ZIP", tmp_path / "missing.zip")
    monkeypatch.setattr(importer, "ARTIFACT_ID", tmp_path / "missing.id")
    assert importer.main() == 0


def test_public_http_get_uses_lightweight_sealed_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel = object()

    class FakeTransport:
        @staticmethod
        def runtime_network_mode() -> str:
            return "enabled"

        @staticmethod
        def sync_get(**kwargs):
            assert kwargs["url"] == "https://api.github.com/example"
            return sentinel

    monkeypatch.setattr(runtime_effects, "_http_transport_module", lambda: FakeTransport)
    monkeypatch.setattr(
        runtime_effects,
        "_effects_impl",
        lambda: (_ for _ in ()).throw(AssertionError("full Effects runtime must not load")),
    )
    assert runtime_effects.http_get(url="https://api.github.com/example", headers={}) is sentinel

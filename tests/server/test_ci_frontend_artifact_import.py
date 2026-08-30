from __future__ import annotations

import fcntl
import hashlib
import io
import json
import os
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


def test_main_does_not_consume_staged_pair_outside_production(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    artifact_zip = tmp_path / "frontend-dist.zip"
    artifact_id = tmp_path / "frontend-dist.artifact-id"
    artifact_zip.write_bytes(b"staged")
    artifact_id.write_text("123", encoding="ascii")
    monkeypatch.setattr(importer, "DIST", tmp_path / "checkout" / "frontend" / "dist")
    monkeypatch.setattr(importer, "ARTIFACT_ZIP", artifact_zip)
    monkeypatch.setattr(importer, "ARTIFACT_ID", artifact_id)
    assert importer.main() == 0
    assert artifact_zip.read_bytes() == b"staged"
    assert artifact_id.read_text(encoding="ascii") == "123"


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


def test_assert_deploy_lock_accepts_expected_locked_fd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    lock_path = tmp_path / "deploy.lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        monkeypatch.setattr(importer, "DEPLOY_LOCK", lock_path)
        importer._assert_deploy_lock(fd)
    finally:
        os.close(fd)


def test_assert_deploy_lock_rejects_wrong_fd_target(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    expected = tmp_path / "expected.lock"
    expected.touch()
    other = tmp_path / "other.lock"
    fd = os.open(other, os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        monkeypatch.setattr(importer, "DEPLOY_LOCK", expected)
        with pytest.raises(RuntimeError, match="does not reference"):
            importer._assert_deploy_lock(fd)
    finally:
        os.close(fd)


def test_production_checkout_sha_reads_symbolic_head(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "checkout"
    git_dir = root / ".git"
    ref = git_dir / "refs" / "heads" / "main"
    ref.parent.mkdir(parents=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="ascii")
    ref.write_text(f"{SHA}\n", encoding="ascii")
    monkeypatch.setattr(importer, "PRODUCTION_ROOT", root)
    assert importer._production_checkout_sha() == SHA


def test_production_checkout_sha_reads_linked_worktree_private_ref(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "checkout"
    common = tmp_path / "repo.git"
    git_dir = common / "worktrees" / "prod"
    git_dir.mkdir(parents=True)
    common.mkdir(exist_ok=True)
    root.mkdir()
    (root / ".git").write_text(f"gitdir: {git_dir}\n", encoding="utf-8")
    (git_dir / "HEAD").write_text("ref: refs/worktree/prod\n", encoding="ascii")
    (git_dir / "commondir").write_text("../..\n", encoding="utf-8")
    private_ref = git_dir / "refs" / "worktree" / "prod"
    private_ref.parent.mkdir(parents=True)
    private_ref.write_text(f"{SHA}\n", encoding="ascii")
    monkeypatch.setattr(importer, "PRODUCTION_ROOT", root)
    assert importer._production_checkout_sha() == SHA


def test_production_checkout_sha_reads_packed_ref(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "checkout"
    git_dir = root / ".git"
    git_dir.mkdir(parents=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="ascii")
    (git_dir / "packed-refs").write_text(f"{SHA} refs/heads/main\n", encoding="ascii")
    monkeypatch.setattr(importer, "PRODUCTION_ROOT", root)
    assert importer._production_checkout_sha() == SHA


def test_main_rejects_expected_sha_different_from_checkout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    artifact_zip = tmp_path / "frontend-dist.zip"
    artifact_id = tmp_path / "frontend-dist.artifact-id"
    artifact_zip.write_bytes(b"staged")
    artifact_id.write_text("123", encoding="ascii")
    monkeypatch.setattr(importer, "DIST", importer.PRODUCTION_ROOT / "frontend" / "dist")
    monkeypatch.setattr(importer, "ARTIFACT_ZIP", artifact_zip)
    monkeypatch.setattr(importer, "ARTIFACT_ID", artifact_id)
    monkeypatch.setenv("EXPECTED_SHA", SHA)
    monkeypatch.setattr(importer, "_assert_deploy_lock", lambda: None)
    monkeypatch.setattr(importer, "_production_checkout_sha", lambda: "b" * 40)
    monkeypatch.setattr(importer, "_validate_metadata", lambda *_args: pytest.fail("metadata must not run"))
    with pytest.raises(RuntimeError, match="does not match EXPECTED_SHA"):
        importer.main()


def test_main_revalidates_checkout_immediately_before_publication(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "prod"
    dist = root / "frontend" / "dist"
    dist.mkdir(parents=True)
    artifact_zip = tmp_path / "frontend-dist.zip"
    artifact_id = tmp_path / "frontend-dist.artifact-id"
    artifact_zip.write_bytes(b"staged")
    artifact_id.write_text("123", encoding="ascii")
    monkeypatch.setattr(importer, "PRODUCTION_ROOT", root)
    monkeypatch.setattr(importer, "DIST", dist)
    monkeypatch.setattr(importer, "ARTIFACT_ZIP", artifact_zip)
    monkeypatch.setattr(importer, "ARTIFACT_ID", artifact_id)
    monkeypatch.setenv("EXPECTED_SHA", SHA)
    observed = iter((SHA, "b" * 40))
    monkeypatch.setattr(importer, "_production_checkout_sha", lambda: next(observed))
    monkeypatch.setattr(importer, "_assert_deploy_lock", lambda: None)
    monkeypatch.setattr(importer, "_validate_metadata", lambda *_args: None)
    monkeypatch.setattr(importer, "_validate_and_extract", lambda *_args: None)
    monkeypatch.setattr(importer, "_exchange_directories", lambda *_args: pytest.fail("swap must not run"))
    with pytest.raises(RuntimeError, match="changed .* before frontend publication"):
        importer.main()


def test_prepare_serving_permissions_before_publish(tmp_path: Path) -> None:
    root = tmp_path / "staged"
    assets = root / "assets"
    assets.mkdir(parents=True)
    index = root / "index.html"
    asset = assets / "app.js"
    index.write_text("ok", encoding="utf-8")
    asset.write_text("ok", encoding="utf-8")
    root.chmod(0o700)
    assets.chmod(0o700)
    index.chmod(0o600)
    asset.chmod(0o600)
    importer._prepare_serving_permissions(root)
    assert root.stat().st_mode & 0o777 == 0o755
    assert assets.stat().st_mode & 0o777 == 0o755
    assert index.stat().st_mode & 0o777 == 0o644
    assert asset.stat().st_mode & 0o777 == 0o644


def test_exchange_directories_is_atomic_namespace_swap(tmp_path: Path) -> None:
    if importer.os.name != "posix":
        pytest.skip("renameat2 exchange is a POSIX production primitive")
    staged = tmp_path / "staged"
    live = tmp_path / "live"
    staged.mkdir()
    live.mkdir()
    (staged / "marker").write_text("new", encoding="utf-8")
    (live / "marker").write_text("old", encoding="utf-8")
    importer._exchange_directories(staged, live)
    assert (live / "marker").read_text(encoding="utf-8") == "new"
    assert (staged / "marker").read_text(encoding="utf-8") == "old"

from __future__ import annotations

from pathlib import Path

from scripts.ci import check_requirements_lock as lock


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _bind_paths(monkeypatch, tmp_path: Path) -> tuple[Path, Path, Path]:
    requirements = _write(
        tmp_path / "requirements.txt",
        "fastapi==0.115.0\nuvicorn[standard]==0.34.2\n",
    )
    top_lock = _write(
        tmp_path / "requirements.lock.txt",
        "# Locked top-level dependencies for reproducible installs.\nfastapi==0.115.0\nuvicorn[standard]==0.34.2\n",
    )
    release_lock = tmp_path / "requirements.release.lock.txt"
    monkeypatch.setattr(lock, "REQUIREMENTS", requirements)
    monkeypatch.setattr(lock, "TOP_LEVEL_LOCK", top_lock)
    monkeypatch.setattr(lock, "RELEASE_REQUIREMENTS_LOCK", release_lock)
    monkeypatch.setattr(lock, "UV_LOCK", tmp_path / "uv.lock")
    monkeypatch.setattr(lock, "POETRY_LOCK", tmp_path / "poetry.lock")
    return requirements, top_lock, release_lock


def test_top_level_lock_preserves_exact_direct_dependency_contract(tmp_path: Path, monkeypatch) -> None:
    _bind_paths(monkeypatch, tmp_path)

    ok, message = lock._check_top_level_lock()

    assert ok is True
    assert "2 direct dependencies" in message


def test_release_gate_rejects_missing_transitive_lock(tmp_path: Path, monkeypatch) -> None:
    _bind_paths(monkeypatch, tmp_path)

    ok, message = lock._check_release_lock()

    assert ok is False
    assert "release requires a transitive lock" in message


def test_release_requirements_lock_allows_transitive_entries(tmp_path: Path, monkeypatch) -> None:
    _, _, release_lock = _bind_paths(monkeypatch, tmp_path)
    _write(
        release_lock,
        "# BAIOS_TRANSITIVE_LOCK: true\nfastapi==0.115.0\nuvicorn[standard]==0.34.2\nstarlette==0.38.6\n",
    )

    ok, message = lock._check_release_lock()

    assert ok is True
    assert "requirements release lock present" in message


def test_release_requirements_lock_rejects_top_level_only_marker(tmp_path: Path, monkeypatch) -> None:
    _, _, release_lock = _bind_paths(monkeypatch, tmp_path)
    _write(
        release_lock,
        "# Locked top-level dependencies for reproducible installs.\nfastapi==0.115.0\nuvicorn[standard]==0.34.2\n",
    )

    ok, message = lock._check_release_lock()

    assert ok is False
    assert "top-level-only" in message

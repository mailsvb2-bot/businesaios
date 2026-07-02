from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = ROOT / "Dockerfile"
RELEASE_LOCK = ROOT / "requirements.release.lock.txt"


def test_container_installs_from_release_transitive_lock() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")

    assert "COPY requirements.release.lock.txt" in text
    assert "pip install --require-hashes -r requirements.release.lock.txt" in text
    assert "BAIOS_REQUIRE_TRANSITIVE_DEPENDENCY_LOCK=1" in text
    assert "pip install -r requirements.lock.txt" not in text
    assert "COPY requirements.lock.txt" not in text


def test_release_lock_contains_transitive_hash_evidence() -> None:
    text = RELEASE_LOCK.read_text(encoding="utf-8")

    assert "BAIOS_TRANSITIVE_LOCK: true" in text
    assert "--hash=sha256:" in text
    assert "Transitive dependency locking can be added later" not in text

from __future__ import annotations

import re
from pathlib import Path

from scripts.ci import check_requirements_lock

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


def test_container_release_install_path_forces_release_lock_validation() -> None:
    assert check_requirements_lock._container_install_requires_release_lock()
    ok, message = check_requirements_lock._check_release_lock()
    assert ok, message


def test_release_gate_rejects_unhashed_or_unpinned_transitive_entries(tmp_path, monkeypatch) -> None:
    original = RELEASE_LOCK.read_text(encoding="utf-8")
    match = re.search(r"^aiofiles==[^\s]+", original, re.M)
    assert match is not None
    pin = match.group()
    assert original.count(pin) == 1
    hash_match = re.search(r"--hash=sha256:[a-f0-9]{64}", original)
    assert hash_match is not None
    corruptions = (
        original.replace(pin + " " + chr(92), pin, 1),
        original.replace(pin, pin.replace("==", ">="), 1),
        original.replace(hash_match.group(), "--hash=sha256:invalid", 1),
        original + "\nrogue==1.0\n",
    )
    for corrupted in corruptions:
        path = tmp_path / "release.lock"
        path.write_text(corrupted, encoding="utf-8")
        monkeypatch.setattr(check_requirements_lock, "RELEASE_REQUIREMENTS_LOCK", path)
        valid, message = check_requirements_lock._check_release_lock()
        assert not valid and "unpinned or unhashed" in message


def test_release_gate_rejects_direct_version_drift_and_duplicate_pin(tmp_path, monkeypatch) -> None:
    original = RELEASE_LOCK.read_text(encoding="utf-8")
    match = re.search(r"^aiogram==[^\s]+", original, re.M)
    assert match is not None
    pin = match.group()
    assert original.count(pin) == 1
    corruptions = (
        original.replace(pin, "aiogram==0.0.0", 1),
        original + "\naiogram==0.0.0 --hash=sha256:" + "0" * 64 + "\n",
    )
    for corrupted in corruptions:
        path = tmp_path / "release.lock"
        path.write_text(corrupted, encoding="utf-8")
        monkeypatch.setattr(check_requirements_lock, "RELEASE_REQUIREMENTS_LOCK", path)
        valid, message = check_requirements_lock._check_release_lock()
        assert not valid and "mismatched or duplicate" in message


def test_release_gate_rejects_marker_without_transitive_dependencies(tmp_path, monkeypatch) -> None:
    direct = check_requirements_lock.REQUIREMENTS.read_text(encoding="utf-8").splitlines()
    fake_lock = "# BAIOS_TRANSITIVE_LOCK: true\n" + "\n".join(
        f"{pin} --hash=sha256:{'0' * 64}" for pin in direct if pin and not pin.startswith("#")
    )
    path = tmp_path / "release.lock"
    path.write_text(fake_lock, encoding="utf-8")
    monkeypatch.setattr(check_requirements_lock, "RELEASE_REQUIREMENTS_LOCK", path)
    valid, message = check_requirements_lock._check_release_lock()
    assert not valid and "transitive dependency" in message

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.ci.encrypted_backup import EncryptedBackupError, open_backup, seal_backup


KEY_HEX = "11" * 32
SHA = "a" * 40


def test_encrypted_backup_round_trip_binds_exact_sha(tmp_path: Path) -> None:
    source = tmp_path / "backup.dump"
    sealed = tmp_path / "backup.dump.enc"
    restored = tmp_path / "restored.dump"
    source.write_bytes(b"postgres-custom-backup")

    digest = seal_backup(source=source, output=sealed, key_hex=KEY_HEX, exact_sha=SHA)
    assert sealed.read_bytes() != source.read_bytes()
    assert len(digest) == 64

    opened_digest = open_backup(
        source=sealed,
        output=restored,
        key_hex=KEY_HEX,
        exact_sha=SHA,
    )
    assert opened_digest == digest
    assert restored.read_bytes() == source.read_bytes()


def test_encrypted_backup_rejects_tamper(tmp_path: Path) -> None:
    source = tmp_path / "backup.dump"
    sealed = tmp_path / "backup.dump.enc"
    restored = tmp_path / "restored.dump"
    source.write_bytes(b"postgres-custom-backup")
    seal_backup(source=source, output=sealed, key_hex=KEY_HEX, exact_sha=SHA)

    payload = bytearray(sealed.read_bytes())
    payload[-1] ^= 1
    sealed.write_bytes(bytes(payload))

    with pytest.raises(EncryptedBackupError, match="authentication failed"):
        open_backup(source=sealed, output=restored, key_hex=KEY_HEX, exact_sha=SHA)
    assert not restored.exists()


def test_encrypted_backup_rejects_wrong_valid_key(tmp_path: Path) -> None:
    source = tmp_path / "backup.dump"
    sealed = tmp_path / "backup.dump.enc"
    restored = tmp_path / "restored.dump"
    source.write_bytes(b"postgres-custom-backup")
    seal_backup(source=source, output=sealed, key_hex=KEY_HEX, exact_sha=SHA)

    with pytest.raises(EncryptedBackupError, match="authentication failed"):
        open_backup(
            source=sealed,
            output=restored,
            key_hex="22" * 32,
            exact_sha=SHA,
        )
    assert not restored.exists()


def test_encrypted_backup_rejects_wrong_sha_binding(tmp_path: Path) -> None:
    source = tmp_path / "backup.dump"
    sealed = tmp_path / "backup.dump.enc"
    restored = tmp_path / "restored.dump"
    source.write_bytes(b"postgres-custom-backup")
    seal_backup(source=source, output=sealed, key_hex=KEY_HEX, exact_sha=SHA)

    with pytest.raises(EncryptedBackupError, match="authentication failed"):
        open_backup(
            source=sealed,
            output=restored,
            key_hex=KEY_HEX,
            exact_sha="b" * 40,
        )
    assert not restored.exists()


@pytest.mark.parametrize("key_hex", ["", "aa", "zz" * 32])
def test_encrypted_backup_rejects_invalid_keys(tmp_path: Path, key_hex: str) -> None:
    source = tmp_path / "backup.dump"
    source.write_bytes(b"postgres-custom-backup")
    with pytest.raises(EncryptedBackupError):
        seal_backup(
            source=source,
            output=tmp_path / "backup.dump.enc",
            key_hex=key_hex,
            exact_sha=SHA,
        )

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

CANON_ENCRYPTED_BACKUP_EVIDENCE = True
_MAGIC = b"BAIOSBK1"
_NONCE_BYTES = 12
_KEY_BYTES = 32


class EncryptedBackupError(RuntimeError):
    pass


def _key_from_hex(value: str) -> bytes:
    try:
        key = bytes.fromhex(str(value or "").strip())
    except ValueError as exc:
        raise EncryptedBackupError("invalid backup encryption key") from exc
    if len(key) != _KEY_BYTES:
        raise EncryptedBackupError("backup encryption key must be 32 bytes")
    return key


def _aad(exact_sha: str) -> bytes:
    token = str(exact_sha or "").strip().lower()
    if len(token) != 40 or any(ch not in "0123456789abcdef" for ch in token):
        raise EncryptedBackupError("exact SHA is required for backup binding")
    return ("businesaios-backup:" + token).encode("ascii")


def seal_backup(*, source: Path, output: Path, key_hex: str, exact_sha: str) -> str:
    plaintext = source.read_bytes()
    if not plaintext:
        raise EncryptedBackupError("backup source is empty")
    key = _key_from_hex(key_hex)
    nonce = os.urandom(_NONCE_BYTES)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, _aad(exact_sha))
    payload = _MAGIC + nonce + ciphertext
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def open_backup(*, source: Path, output: Path, key_hex: str, exact_sha: str) -> str:
    payload = source.read_bytes()
    minimum = len(_MAGIC) + _NONCE_BYTES + 16
    if len(payload) < minimum or not payload.startswith(_MAGIC):
        raise EncryptedBackupError("invalid encrypted backup envelope")
    key = _key_from_hex(key_hex)
    nonce_start = len(_MAGIC)
    nonce = payload[nonce_start : nonce_start + _NONCE_BYTES]
    ciphertext = payload[nonce_start + _NONCE_BYTES :]
    try:
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, _aad(exact_sha))
    except Exception as exc:
        raise EncryptedBackupError("encrypted backup authentication failed") from exc
    if not plaintext:
        raise EncryptedBackupError("decrypted backup is empty")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(plaintext)
    return hashlib.sha256(payload).hexdigest()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("seal", "open"):
        item = sub.add_parser(name)
        item.add_argument("--source", type=Path, required=True)
        item.add_argument("--output", type=Path, required=True)
        item.add_argument("--key-hex", required=True)
        item.add_argument("--exact-sha", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        digest = (
            seal_backup(
                source=args.source,
                output=args.output,
                key_hex=args.key_hex,
                exact_sha=args.exact_sha,
            )
            if args.command == "seal"
            else open_backup(
                source=args.source,
                output=args.output,
                key_hex=args.key_hex,
                exact_sha=args.exact_sha,
            )
        )
    except (OSError, EncryptedBackupError) as exc:
        print(f"[encrypted-backup] blocked: {exc}")
        return 2
    print(digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CANON_ENCRYPTED_BACKUP_EVIDENCE",
    "EncryptedBackupError",
    "open_backup",
    "seal_backup",
]
